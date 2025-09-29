from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Show the CustomUser with the extra 'role' and 'grade_class' fields 
    and keep the standard Django auth admin behavior.
    """

    # --- MUUTETUT KOHDAT ---

    # 1. Lisätty 'grade_class' listanäkymään
    list_display = ("username", "email", "first_name", "last_name", "role", "grade_class", "is_staff", "is_active")
    
    # 2. Lisätty 'grade_class' suodattimiin
    list_filter = ("role", "grade_class", "is_staff", "is_superuser", "is_active")

    # 3. Sallitaan luokan muokkaus suoraan listasta
    list_editable = ("grade_class",)

    # 4. Lisätty 'grade_class' muokkaus- ja lisäysnäkymiin 'role'-kentän viereen
    fieldsets = UserAdmin.fieldsets + (
        ("Rooli ja luokka", {"fields": ("role", "grade_class")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rooli ja luokka", {"fields": ("role", "grade_class")}),
    )

    # --- AIEMMAT ASETUKSET (säilytetty) ---
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)