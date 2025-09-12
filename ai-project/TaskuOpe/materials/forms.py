from django import forms

# Import the models we need to build forms from
from .models import Material, Submission, Assignment
from users.models import CustomUser


class MaterialForm(forms.ModelForm):
    """
    Manuaalinen materiaalin luonti (suomennetut labelit).
    """
    class Meta:
        model = Material
        fields = ["title", "content", "material_type", "subject", "grade_level"]

        # 🔹 SUOMENNETUT OTSIKOT
        labels = {
            "title": "Otsikko",
            "content": "Sisältö",
            "subject": "Aihe",
            "grade_level": "Kohderyhmä / luokka-aste",
            "material_type": "Materiaalin tyyppi",
        }

        # 🔹 Isompi tekstialue + suomenkieliset placeholderit
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Esim. Jakokulma – alkeet"
            }),
            "content": forms.Textarea(attrs={
                "rows": 12,
                "placeholder": "Kirjoita tai liitä materiaalin sisältö..."
            }),
            "subject": forms.TextInput(attrs={
                "placeholder": "Esim. Matematiikka"
            }),
            "grade_level": forms.TextInput(attrs={
                "placeholder": "Esim. 7. luokka"
            }),
        }


class AssignmentForm(forms.Form):
    """
    Opettaja: anna materiaali usealle opiskelijalle.
    """
    students = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),  # asetetaan dynaamisesti __init__:ssä
        widget=forms.CheckboxSelectMultiple,
        label="Valitse opiskelijat",
        required=True,
        help_text="Valitse yksi tai useampi opiskelija."
    )

    due_at = forms.DateTimeField(
        label="Määräaika (valinnainen)",
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "placeholder": "YYYY-MM-DD HH:MM",
            }
        ),
        help_text="Selaimesi käyttää paikallista aikavyöhykettä."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Haetaan opiskelijat vasta tässä vaiheessa (aina ajantasainen queryset)
        self.fields["students"].queryset = CustomUser.objects.filter(role="STUDENT").order_by("username")


class SubmissionForm(forms.ModelForm):
    """
    A form for a student to submit their response to an assignment.
    """
    class Meta:
        model = Submission
        # The student only needs to fill out the 'response' field
        fields = ['response']
        widgets = {
            'response': forms.Textarea(attrs={
                'rows': 10, 
                'class': 'form-control', 
                'placeholder': 'Kirjoita vastauksesi tähän...'
            }),
        }
        labels = {
            'response': 'Vastauksesi (Your Response)'
        }

from decimal import Decimal, InvalidOperation
from django import forms
from .models import Submission

class GradingForm(forms.ModelForm):
    # 4–10 vaihtoehdot + tyhjä
    GRADE_CHOICES = [(n, str(n)) for n in range(4, 11)]
    grade = forms.TypedChoiceField(
        choices=[('', '— Ei arvosanaa —')] + GRADE_CHOICES,
        required=False,
        label="Arvosana (4–10) – valinnainen",
        coerce=lambda v: int(v) if v not in (None, '',) else None,
        empty_value=None,
    )

    # ⬇️ huomaa nimet: score ja max_score (samat kuin mallissa)
    score = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=6,
        label="Saadut pisteet",
        widget=forms.NumberInput(attrs={"step": "0.5", "placeholder": "esim. 17"})
    )
    max_score = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=6,
        label="Maksimipisteet",
        widget=forms.NumberInput(attrs={"step": "0.5", "placeholder": "esim. 20"})
    )

    feedback = forms.CharField(
        required=False, label="Palaute",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Avoin palaute oppilaalle…"})
    )

    class Meta:
        model = Submission
        fields = ["grade", "score", "max_score", "feedback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        self.fields["grade"].initial = str(instance.grade) if instance and instance.grade is not None else ''

    # Salli pilkku desimaalina
    def _to_decimal(self, val):
        if val in (None, ''):
            return None
        if isinstance(val, str):
            val = val.replace(',', '.')
        try:
            return Decimal(val)
        except (InvalidOperation, TypeError, ValueError):
            raise forms.ValidationError("Anna kelvollinen numero (voit käyttää pilkkua).")

    def clean_score(self):
        return self._to_decimal(self.cleaned_data.get("score"))

    def clean_max_score(self):
        return self._to_decimal(self.cleaned_data.get("max_score"))

    def clean(self):
        cleaned = super().clean()
        s = cleaned.get("score")
        m = cleaned.get("max_score")
        if s is not None and m is not None and s > m:
            self.add_error("score", "Saadut pisteet eivät voi ylittää maksimipisteitä.")
        return cleaned
