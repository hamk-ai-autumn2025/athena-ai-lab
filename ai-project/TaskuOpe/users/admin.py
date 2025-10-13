# ai-project/users/admin.py

"""
Määrittelee CustomUser-mallin hallintapaneelin asetukset.

Tässä tiedostossa rekisteröidään CustomUser-malli Djangon
ylläpitopaneeliin ja määritellään sen ulkoasu ja toiminnallisuus,
kuten käytettävät lomakkeet, näytettävät kentät ja suodatusvaihtoehdot.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Djangon ylläpitopaneelin määritys CustomUser-mallille.

    Käyttää omia, turvallisia lomakkeita (CustomUserCreationForm, CustomUserChangeForm)
    ja näyttää kaikki halutut kentät (kuten `role`, `grade_class`, `email`)
    sekä lista- että muokkausnäkymissä.
    """

    # --- UUDET, TIETOTURVAA PARANTAVAT LISÄYKSET ---
    # Nämä ottavat omat lomakkeesi käyttöön admin-paneelissa.
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    # --- OLEMASSA OLEVAT, HYVÄT ASETUKSESI (SÄILYTETTY) ---
    list_display = ("username", "email", "first_name", "last_name", "role", "grade_class", "is_staff", "is_active")
    list_filter = ("role", "grade_class", "is_staff", "is_superuser", "is_active")
    list_editable = ("grade_class",)
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    # --- PÄIVITETYT KENTTÄMÄÄRITYKSET ---

    # 1. Muokkausnäkymä (fieldsets) on jo kunnossa, säilytetään se ennallaan.
    fieldsets = UserAdmin.fieldsets + (
        ("Rooli ja luokka", {"fields": ("role", "grade_class")}),
    )

    # 2. Uuden käyttäjän luontinäkymä (add_fieldsets) on nyt TÄYDENNETTY.

    # HUOM: Tässä määritellään add_fieldsets kokonaan uudelleen (ei peritä UserAdmin.add_fieldsets).
    # Aiemmin perintä toi mukanaan virheellisen 'usable_password'-kentän, jota CustomUser-mallissa ei ole.
    # Tämä korjaus poistaa sen ja määrittää uuden käyttäjän luontinäkymän kentät selkeästi ja oikein. //ida
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2"),  # tai ("email", "password1", "password2")
        }),
        ("Käyttäjän perustiedot", {
            "fields": ("first_name", 
                       "last_name", 
                       "email", 
                       "role", 
                       "grade_class"),
        }),
    )