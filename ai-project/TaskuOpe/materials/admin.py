from django.contrib import admin
from .models import Material

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "author")
    list_filter = ("author",)
    search_fields = ("title", "description", "author__username", "author__email")
