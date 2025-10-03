# ai-project/users/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm

from .models import CustomUser

class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget.attrs.update({
            'class': 'form-control'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control'
        })

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        # Nämä kentät näkyvät add_form-lomakkeessa
        fields = ('username', 'first_name', 'last_name', 'email', 'role')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if " " in username:
            raise forms.ValidationError("Käyttäjätunnus ei saa sisältää välilyöntejä.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = True
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        # Nämä kentät näkyvät olemassa olevan käyttäjän muokkauslomakkeessa
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'grade_class', 'is_active', 'is_staff')