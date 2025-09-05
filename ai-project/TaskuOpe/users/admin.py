from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Show the CustomUser with the extra 'role' field and keep the standard
    Django auth admin behavior.
    """

    # Columns in the changelist
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")

    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    # Add the 'role' field into the existing fieldsets (edit page)
    fieldsets = UserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )

    # Add the 'role' field into the add-user page
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
