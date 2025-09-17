from django import forms
from decimal import Decimal, InvalidOperation

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

    # This method adds the custom placeholders to the dropdowns
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # For the Class Grade dropdown
        grade_choices = self.fields['grade_level'].choices
        self.fields['grade_level'].choices = [('', 'Valitse luokka')] + list(grade_choices)[1:]

        # For the Material Type dropdown
        type_choices = self.fields['material_type'].choices
        self.fields['material_type'].choices = [('', 'Valitse materiaalin tyyppi')] + list(type_choices)[1:]


class AssignmentForm(forms.Form):
    """
    Opettaja: anna materiaali usealle opiskelijalle.
    """
    students = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled'}),
        label="Valitse opiskelijat",
        required=True,
    )

    due_at = forms.DateTimeField(
        label="Määräaika (valinnainen)",
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = CustomUser.objects.filter(role="STUDENT").order_by("username")


class SubmissionForm(forms.ModelForm):
    """
    A form for a student to submit their response to an assignment.
    """
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
        widget=forms.Select(attrs={
            "class": "form-select w-100"
        })
    )
    score = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=6,
        label="Saadut pisteet",
        widget=forms.NumberInput(attrs={
            "step": "0.5",
            "placeholder": "esim. 17",
            "class": "form-control w-100"
        })
    )
    max_score = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=6,
        label="Maksimipisteet",
        widget=forms.NumberInput(attrs={
            "step": "0.5",
            "placeholder": "esim. 20",
            "class": "form-control w-100"
        })
    )
    feedback = forms.CharField(
        required=False,
        label="Palaute",
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "Avoin palaute oppilaalle…",
            "class": "form-control w-100"
        })
    )

    class Meta:
        model = Submission
        fields = ["grade", "score", "max_score", "feedback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        self.fields["grade"].initial = str(instance.grade) if instance and instance.grade is not None else ''