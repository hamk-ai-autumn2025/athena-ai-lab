from django import forms
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

# Import the models we need to build forms from
from .models import Material, Submission, Assignment
from django.contrib.auth import get_user_model


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["title", "content", "material_type", "subject", "grade_level"]
        labels = {
            "title": "Otsikko",
            "content": "Sisältö",
            "subject": "Aihe",
            "grade_level": "Kohderyhmä / luokka-aste",
            "material_type": "Materiaalin tyyppi",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Esim. Jakokulma – alkeet", "class": "form-control"}),
            "content": forms.Textarea(attrs={"rows": 12, "placeholder": "Kirjoita tai liitä materiaalin sisältö...", "class": "form-control"}),
            "subject": forms.TextInput(attrs={"placeholder": "Esim. Matematiikka", "class": "form-control"}),
            "material_type": forms.Select(attrs={"class": "form-select"}),
            "grade_level": forms.Select(attrs={"class": "form-select"}),
        }

    # KORJATTU: Molemmat aiemmat __init__-metodit on nyt yhdistetty tähän yhteen.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Lisää "Valitse luokka" -vaihtoehdon pudotusvalikkoon
        grade_choices = self.fields['grade_level'].choices
        self.fields['grade_level'].choices = [('', 'Valitse luokka')] + list(grade_choices)[1:]

        # Lisää "Valitse materiaalin tyyppi" -vaihtoehdon pudotusvalikkoon
        type_choices = self.fields['material_type'].choices
        self.fields['material_type'].choices = [('', 'Valitse materiaalin tyyppi')] + list(type_choices)[1:]


class AssignmentForm(forms.Form):
    """
    Tätä käytetään (jos käytetään) yksittäisen tehtävän jakoon opiskelijoille.
    """
    students = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled'}),
        label="Valitse opiskelijat",
        required=True,
    )
    due_at = forms.DateTimeField(
        label="Määräaika (valinnainen)",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields["students"].queryset = (
            User.objects.filter(role="STUDENT").order_by("first_name", "last_name", "username")
        )

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['response']
        widgets = {
            'response': forms.Textarea(attrs={'rows': 10, 'class': 'form-control', 'placeholder': 'Kirjoita vastauksesi tähän...'}),
        }
        labels = {'response': 'Vastauksesi (Your Response)'}


class GradingForm(forms.ModelForm):
    GRADE_CHOICES = [(n, str(n)) for n in range(4, 11)]
    grade = forms.TypedChoiceField(
        choices=[('', '— Ei arvosanaa —')] + GRADE_CHOICES,
        required=False,
        label="Arvosana (4–10) – valinnainen",
        coerce=lambda v: int(v) if v not in (None, '',) else None,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select w-100"})
    )
    score = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=6,
        label="Saadut pisteet",
        widget=forms.NumberInput(attrs={"step": "0.5", "placeholder": "esim. 17", "class": "form-control w-100"})
    )
    max_score = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=6,
        label="Maksimipisteet",
        widget=forms.NumberInput(attrs={"step": "0.5", "placeholder": "esim. 20", "class": "form-control w-100"})
    )
    feedback = forms.CharField(
        required=False,
        label="Palaute",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Avoin palaute oppilaalle…", "class": "form-control w-100"})
    )

    class Meta:
        model = Submission
        fields = ["grade", "score", "max_score", "feedback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        self.fields["grade"].initial = str(instance.grade) if instance and instance.grade is not None else ''

    # LISÄTTY: Kenttien välinen validointi, joka estää loogiset virheet.

    def clean(self):
        cleaned_data = super().clean()
        score = cleaned_data.get("score")
        max_score = cleaned_data.get("max_score")

        # Tarkistetaan, että molemmat kentät on täytetty, ennen kuin verrataan
        if score is not None and max_score is not None:
            if score > max_score:
                # KORVATTU: Käytetään add_error-metodia, joka liittää virheen
                # suoraan 'score'-kenttään. Tämä näkyy templaatissa.
                self.add_error('score', "Saadut pisteet eivät voi olla suuremmat kuin maksimipisteet.")
        
        return cleaned_data


class AddImageForm(forms.Form):

    IMAGE_SIZES = (
        ('size-medium', 'Keskikokoinen (oletus)'),
        ('size-small', 'Pieni'),
        ('size-large', 'Suuri'),
    )

    ALIGN_CHOICES = (
        ('align-center', 'Keskitetty (oletus)'),
        ('align-left', 'Vasen'),
        ('align-right', 'Oikea'),
    )

    upload = forms.ImageField(required=False, label="Lataa kuva")
    gen_prompt = forms.CharField(
        required=False, 
        label="Kuvaile generoitu kuva",
        max_length=1000, 
        widget=forms.Textarea(attrs={'rows': 3})
    )
    caption = forms.CharField(required=False, max_length=255, label="Kuvateksti")
    
    size = forms.ChoiceField(
        choices=IMAGE_SIZES, # <-- Nyt tämä toimii
        required=True,
        label="Kuvan koko sisällössä",
        initial='size-md',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    alignment = forms.ChoiceField(
        choices=ALIGN_CHOICES,
        required=True,
        label="Kuvan sijainti",
        initial='align-center',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("upload") and not cleaned.get("gen_prompt"):
            raise forms.ValidationError("Valitse joko tiedoston lataus tai kirjoita generointikehote.")
        return cleaned


class AssignForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Valitse opiskelijat"
    )
    due_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Määräaika (valinnainen)"
    )
    give_to_class = forms.BooleanField(required=False, label="Anna koko luokalle")
    class_number = forms.TypedChoiceField(
        required=False,
        coerce=int,
        choices=[("", "— Valitse luokka —")] + [(i, f"{i}. luokka") for i in range(1, 7)],
        label="Luokka"
    )

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        qs = User.objects.filter(role="STUDENT")
        # Jos haluat rajata opettajan omiin ryhmiin, tee se tässä:
        # if teacher is not None:
        #     qs = qs.filter(classgroup__teacher=teacher).distinct()
        self.fields["students"].queryset = qs.order_by("username")

