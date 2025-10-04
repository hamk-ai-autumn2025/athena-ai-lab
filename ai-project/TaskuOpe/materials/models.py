# materials/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser

# ↓ lisää nämä importit jos eivät jo ole
from django.db.models.signals import post_delete
from django.dispatch import receiver
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
import re

class Prompt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.TextField(verbose_name=_("Kehoite"))
    model = models.CharField(max_length=100, verbose_name=_("Mallin tunnus"))
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'TEACHER'},
        verbose_name=_("Opettaja"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))

    class Meta:
        verbose_name = _("Kehoite")
        verbose_name_plural = _("Kehoitteet")

    def __str__(self):
        return f"Prompt by {self.teacher.username} at {self.created_at.strftime('%Y-%m-%d')}"


class Material(models.Model):
    class MaterialType(models.TextChoices):
        TASK = 'tehtävä', _('Tehtävä')
        LEARNING_MATERIAL = 'oppimateriaali', _('Oppimateriaali')
        TEST = 'testi', _('Testi')
        EXAM = 'koe', _('Koe')
        VIDEO = 'video', _('Video')
        GAME = 'peli', _('Peli')

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Luonnos')
        PENDING_APPROVAL = 'PENDING', _('Odottaa hyväksyntää')
        APPROVED = 'APPROVED', _('Hyväksytty')
        REJECTED = 'REJECTED', _('Hylätty')

    GRADE_CHOICES = [(str(i), f"{i}. luokka") for i in range(1, 7)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name=_("Otsikko"))
    content = models.TextField(
        verbose_name=_("Sisältö"),
        help_text=_("Raakasisältö, esim. AI:n tuottama teksti.")
    )
    structured_content = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Jäsennelty sisältö"),
        help_text=_("Esim. monivalinnat tai tehtävän rakenne JSON-muodossa.")
    )
    material_type = models.CharField(
        max_length=50,
        choices=MaterialType.choices,
        default=MaterialType.TASK,
        verbose_name=_("Materiaalin tyyppi"),
    )
    subject = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Aine"))
    # Valittava luokka-aste merkkijonona (että choices toimii)
    grade_level = models.CharField(
        max_length=20,
        choices=GRADE_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Luokka-aste"),
    )
    audience = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Kohderyhmä"),
        help_text=_("Esim. {'learning_styles': ['visuaalinen'], 'languages': ['fi']}")
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='authored_materials',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'TEACHER'},
        verbose_name=_("Tekijä (opettaja)"),
    )
    prompt = models.ForeignKey(
        Prompt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Kehoite"),
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Tila"),
    )
    version = models.IntegerField(default=1, verbose_name=_("Versio"))
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versions',
        verbose_name=_("Edellinen versio"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Päivitetty"))

    class Meta:
        verbose_name = _("Materiaali")
        verbose_name_plural = _("Materiaalit")

    def __str__(self):
        return f"{self.title} (v{self.version})"
    
    def save(self, *args, **kwargs):
        """
        Ylikirjoitettu save-metodi, joka varmistaa, että aiheen (subject)
        ensimmäinen kirjain on aina iso.
        """
        # Muunna aiheen ensimmäinen kirjain isoksi, jos aihe on määritelty
        if self.subject:
            self.subject = self.subject.capitalize()
            
        # Kutsu alkuperäistä save-metodia, jotta tallennus tapahtuu oikein
        super().save(*args, **kwargs)


@property
def content_without_images(self):
        """
        Palauttaa sisällön ilman Markdown-kuvalinkkejä ja siistittynä.
        Täydellinen korttien esikatselua varten.
        """
        if not self.content:
            return ""
        # Poistetaan Markdown-kuvat ja ylimääräiset rivinvaihdot
            no_images = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', self.content)
    # Poistetaan peräkkäiset tyhjät rivit ja palautetaan siistitty teksti
            cleaned_text = re.sub(r'\n\s*\n', '\n', no_images).strip()
            return cleaned_text

class MaterialRevision(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='revisions', verbose_name=_("Materiaali"))
    version = models.IntegerField(verbose_name=_("Versio"))
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Muokkaaja"))
    note = models.CharField(max_length=255, blank=True, verbose_name=_("Huomio"))
    diff = models.JSONField(null=True, blank=True, verbose_name=_("Erot (diff)"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Materiaaliversio")
        verbose_name_plural = _("Materiaaliversiot")


class Assignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", _("Annettu")
        IN_PROGRESS = "IN_PROGRESS", _("Kesken")
        SUBMITTED = "SUBMITTED", _("Palautettu")
        GRADED = "GRADED", _("Arvioitu")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name=_("Materiaali"))
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='assignments',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'STUDENT'},
        verbose_name=_("Oppilas"),
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='assigned_tasks',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'TEACHER'},
        verbose_name=_("Antanut opettaja"),
    )
    due_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Määräaika"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED, verbose_name=_("Tila"))
    draft_response = models.TextField(blank=True, null=True, verbose_name=_("Luonnosvastaus"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['material', 'student'], name='unique_assignment_per_student'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['due_at']),
            models.Index(fields=['student']),
            models.Index(fields=['assigned_by']),
        ]
        verbose_name = _("Tehtävänanto")
        verbose_name_plural = _("Tehtävänannot")

    def __str__(self):
        return f"'{self.material.title}' for {self.student.username}"


class Submission(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', _('Kesken')
        SUBMITTED = 'SUBMITTED', _('Palautettu')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assignment = models.ForeignKey('materials.Assignment', on_delete=models.CASCADE, related_name='submissions', verbose_name=_("Tehtävänanto"))
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'STUDENT'},
        verbose_name=_("Oppilas"),
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, verbose_name=_("Tila"))

    # Arvio
    grade = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(4), MaxValueValidator(10)],
        help_text=_("Numeroarvosana 4–10"),
        verbose_name=_("Arvosana"),
    )
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Saadut pisteet"),
        verbose_name=_("Pisteet"),
    )
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Maksimipisteet"),
        verbose_name=_("Maksimipisteet"),
    )
    feedback = models.TextField(blank=True, help_text=_("Opettajan palaute"), verbose_name=_("Palaute"))

    # Oppilaan kirjoittama vastaus
    response = models.TextField(blank=True, verbose_name=_("Vastaus"))

    # Aikaleimat
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))
    started_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Aloitettu"))
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Palautettu"))
    graded_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Arvioitu"))

    class Meta:
        verbose_name = _("Palautus")
        verbose_name_plural = _("Palautukset")

    def __str__(self):
        return f"{self.student} → {self.assignment} ({self.get_status_display()})"


class PlagiarismReport(models.Model):
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="plagiarism_report", verbose_name=_("Palautus"))
    suspected_source = models.ForeignKey(
        Submission,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="plagiarized_by",
        verbose_name=_("Mahdollinen lähde"),
    )
    score = models.FloatField(
        default=0.0,
        help_text=_("AI:n arvioima plagiointiriski (0–1)"),
        verbose_name=_("Plagiointiriski"),
    )
    highlights = models.TextField(
        blank=True,
        help_text=_("AI:n huomiot ja korostukset (HTML tai JSON)"),
        verbose_name=_("Huomiot"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))

    class Meta:
        verbose_name = _("Alkuperäisyysraportti")
        verbose_name_plural = _("Alkuperäisyysraportit")


class Rubric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='rubrics', verbose_name=_("Materiaali"))
    title = models.CharField(max_length=200, default=_("Oletuskriteeristö"), verbose_name=_("Otsikko"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Luonut"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))

    class Meta:
        verbose_name = _("Arviointikriteeristö")
        verbose_name_plural = _("Arviointikriteeristöt")

    def __str__(self):
        return self.title


class RubricCriterion(models.Model):
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name='criteria', verbose_name=_("Kriteeristö"))
    name = models.CharField(max_length=200, verbose_name=_("Kriteeri"))
    max_points = models.PositiveIntegerField(default=5, verbose_name=_("Maksimipisteet"))
    guidance = models.TextField(blank=True, verbose_name=_("Ohjeistus"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Järjestys"))

    class Meta:
        verbose_name = _("Arviointikriteeri")
        verbose_name_plural = _("Arviointikriteerit")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} ({self.max_points}p)"


class AIGrade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name='ai_grade', verbose_name=_("Palautus"))
    rubric = models.ForeignKey(Rubric, on_delete=models.SET_NULL, null=True, verbose_name=_("Kriteeristö"))
    model_name = models.CharField(max_length=100, default="gpt-4o-mini", verbose_name=_("Mallin nimi"))
    total_points = models.FloatField(default=0, verbose_name=_("Yhteispisteet"))
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Yksityiskohdat"),
        help_text=_("Muoto: {'criteria':[{'name','points','max','feedback'}], 'general_feedback': ''}")
    )
    teacher_confirmed = models.BooleanField(default=False, verbose_name=_("Opettaja vahvistanut"))
    teacher_notes = models.TextField(blank=True, verbose_name=_("Opettajan muistiinpanot"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Luotu"))

    class Meta:
        verbose_name = _("AI-arvio")
        verbose_name_plural = _("AI-arviot")

class MaterialImage(models.Model):
    material = models.ForeignKey("Material", related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="materials/%Y/%m/")
    caption = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    # Tämä luo automaattisesti pienennetyn version kuvasta.
    # Se tallennetaan CACHE/images/materials/... -kansioon.
    thumbnail = ImageSpecField(source='image',
                                      processors=[ResizeToFill(400, 250)], # Rajaa kuvan kokoon 400x250
                                      format='JPEG',
                                      options={'quality': 85}) # Pakkaa JPEG-kuvaksi hyvällä laadulla
    def __str__(self):
        return self.caption or self.image.name

# ⬇ HUOM: tämä on luokan ULKOPUOLELLA
@receiver(post_delete, sender=MaterialImage)
def delete_image_file(sender, instance, **kwargs):
    """
    Kun MaterialImage-tietue poistetaan, poista myös kuvatiedosto levystä.
    """
    if instance.image:
        instance.image.delete(save=False)
