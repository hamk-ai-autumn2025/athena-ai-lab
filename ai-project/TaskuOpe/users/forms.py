# ai-project/users/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm

class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add the 'form-control' class to the username field's widget
        self.fields['username'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Käyttäjätunnus'}
        )

        # Add the 'form-control' class to the password field's widget
        self.fields['password'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Salasana'}
        )