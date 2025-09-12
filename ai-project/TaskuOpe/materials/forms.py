from django import forms

# Import the models we need to build forms from
from .models import Material, Submission, Assignment
from users.models import CustomUser


class MaterialForm(forms.ModelForm):
    """
    A form for manually creating or editing a Material.
    Used for testing purposes.
    """
    class Meta:
        model = Material
        # These are the fields a user can fill out directly
        fields = [
            'title', 
            'content', 
            'material_type', 
            'subject', 
            'grade_level'
        ]
        # Make the content box larger for easier typing
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10}),
        }


class AssignmentForm(forms.Form):
    """
    A form for a teacher to assign a material to multiple students.
    """
    # This field dynamically queries for all student users and displays them as checkboxes
    students = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.filter(role='STUDENT'),
        widget=forms.CheckboxSelectMultiple,
        label="Valitse opiskelijat",
        required=True
    )
    
    # This field provides a pop-up calendar/time selector in the browser
    due_at = forms.DateTimeField(
        label="Määräaika (valinnainen)",
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )


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

