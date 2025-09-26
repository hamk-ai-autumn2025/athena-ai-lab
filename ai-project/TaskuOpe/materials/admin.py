# materials/admin.py
from django.contrib import admin
from .models import Prompt, Material, MaterialRevision, Assignment, Submission, PlagiarismReport, Rubric, RubricCriterion, AIGrade

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

@admin.register(PlagiarismReport)
class PlagiarismReportAdmin(admin.ModelAdmin):
    list_display = ("submission", "suspected_source", "score", "created_at")
    search_fields = (
        "submission__id",
        "submission__student__username",
        "suspected_source__id",
        "suspected_source__student__username",
    )
    list_filter = ("created_at",)

class RubricCriterionInline(admin.TabularInline):
    model = RubricCriterion
    extra = 1
    fields = ("name", "max_points", "guidance", "order")

@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("title", "material", "created_by", "created_at")
    inlines = [RubricCriterionInline]
    search_fields = ("title", "material__title", "created_by__username")

@admin.register(AIGrade)
class AIGradeAdmin(admin.ModelAdmin):
    list_display = ("submission", "rubric", "model_name", "total_points", "teacher_confirmed", "created_at")
    search_fields = ("submission__id", "rubric__title", "submission__student__username")
    list_filter = ("teacher_confirmed", "model_name", "created_at")

