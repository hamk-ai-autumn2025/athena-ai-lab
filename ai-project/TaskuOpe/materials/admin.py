# materials/admin.py
from django.contrib import admin
from .models import Prompt, Material, MaterialRevision, Assignment, Submission

class MaterialRevisionInline(admin.TabularInline):
    model = MaterialRevision
    extra = 0 # Don't show extra empty forms

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'version', 'created_at')
    list_filter = ('status', 'material_type', 'author')
    inlines = [MaterialRevisionInline] # Show revisions on the material page

# Register the other models so they are visible in the admin
admin.site.register(Prompt)
admin.site.register(Assignment)
admin.site.register(Submission)