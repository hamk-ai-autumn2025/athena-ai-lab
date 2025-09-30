# ai-project/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
# TUO OMAT LOMAKKEESI
from .forms import CustomUserCreationForm, CustomUserChangeForm

# Käytetään @admin.register-dekoraattoria, kuten aiemminkin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    LOPULLINEN ADMIN-MÄÄRITYS:
    - Käyttää omia, turvallisia lomakkeita (`CustomUserCreationForm`, `CustomUserChangeForm`).
    - Näyttää kaikki halutut kentät (`role`, `grade_class`, `email`, yms.) sekä lista- että muokkausnäkymissä.
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
    #    Tämä näyttää salasanakenttien LISÄKSI myös nimen, sähköpostin ja roolin/luokan.
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Käyttäjän perustiedot",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "role",
                    "grade_class",
                )
            },
        ),
    )