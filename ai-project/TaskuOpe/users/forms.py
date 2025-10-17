# ai-project/users/forms.py
"""
Määrittelee Djangon käyttäjähallintaan liittyvät mukautetut lomakkeet.

Tässä tiedostossa luodaan lomakkeet käyttäjän sisäänkirjautumista,
uuden käyttäjän luomista ja olemassa olevan käyttäjän muokkaamista varten.
Lomakkeet perustuvat Djangon sisäänrakennettuihin todennuslomakkeisiin
ja hyödyntävät CustomUser-mallia.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm

from .models import CustomUser


class CustomLoginForm(AuthenticationForm):
    """
    Mukautettu sisäänkirjautumislomake.

    Perii Djangon oletusarvoisen AuthenticationFormin ja lisää CSS-luokkia
    käyttäjätunnus- ja salasana-kenttiin tyylittelyä varten.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget.attrs.update({
            'class': 'form-control'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control'
        })

class CustomUserCreationForm(UserCreationForm):
    """
    Mukautettu lomake uuden käyttäjän luomiseen.

    Perii Djangon UserCreationFormin ja määrittää CustomUser-mallin
    käytettäväksi. Sisältää myös mukautettuja validointisääntöjä
    ja käyttäjän aktivoinnin.
    """
    class Meta(UserCreationForm.Meta):
        """Metaluokka CustomUserCreationFormille."""
        model = CustomUser
        # Nämä kentät näkyvät add_form-lomakkeessa
        fields = ('username', 'first_name', 'last_name', 'email', 'role')

    def clean_username(self):
        """
        Validoi käyttäjätunnuksen varmistaen, ettei se sisällä välilyöntejä.

        Raises:
            forms.ValidationError: Jos käyttäjätunnus sisältää välilyöntejä.

        Returns:
            Validoitu käyttäjätunnus.
        """
        username = self.cleaned_data.get('username')
        if " " in username:
            raise forms.ValidationError("Käyttäjätunnus ei saa sisältää välilyöntejä.")
        return username

    def save(self, commit=True):
        """
        Tallentaa uuden käyttäjän ja asettaa `is_active`-kentän Trueksi.

        Args:
            commit: Bool-arvo, joka määrittää tallennetaanko käyttäjä
                    tietokantaan heti vai palautetaanko malliesiintymä.

        Returns:
            Luotu tai alustettu CustomUser-objekti.
        """
        user = super().save(commit=False)
        user.is_active = True
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    """
    Mukautettu lomake olemassa olevan käyttäjän muokkaamiseen.

    Perii Djangon UserChangeFormin ja määrittää CustomUser-mallin
    käytettäväksi. Määrittelee myös kentät, jotka näytetään
    käyttäjän muokkauslomakkeessa.
    """
    class Meta:
        """Metaluokka CustomUserChangeFormille."""
        model = CustomUser
        # Nämä kentät näkyvät olemassa olevan käyttäjän muokkauslomakkeessa
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'grade_class', 'is_active', 'is_staff')

# --- LOMAKE PROFIILIKUVALLE ---
class ProfileImageForm(forms.ModelForm):
    """Lomake profiilikuvan päivittämistä varten."""
    class Meta:
        model = CustomUser
        fields = ['profile_image']
        labels = {
            # Piilotetaan erillinen otsikko, koska se on nyt osana ulkoasua
            'profile_image': ''
        }
        # Lisätään widget-määritys, jotta kenttään tulee oikeat CSS-luokat
        widgets = {
            'profile_image': forms.FileInput(attrs={'class': 'form-control'})
        }