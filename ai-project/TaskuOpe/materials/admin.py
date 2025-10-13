# materials/admin.py
from django.contrib import admin

from .models import (
    AIGrade,
    Assignment,
    Material,
    MaterialRevision,
    PlagiarismReport,
    Prompt,
    Rubric,
    RubricCriterion,
    Submission,
)


class MaterialRevisionInline(admin.TabularInline):
    """
    Määrittää MaterialRevision-mallin inline-esittämisen Material-muokkaussivulla.
    Mahdollistaa materiaaliversioiden hallinnan suoraan päämateriaalinäkymästä.
    """
    model = MaterialRevision
    extra = 0  # Don't show extra empty forms


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    """
    Määrittää Material-mallin hallintanäkymän Django-ylläpitäjän puolella.
    Näyttää materiaalit listana otsikon, tekijän, tilan, version ja luontiajan mukaan.
    Tarjoaa suodatusmahdollisuudet tilan, tyypin ja tekijän perusteella
    ja integroi MaterialRevision-inlinet.
    """
    list_display = ('title', 'author', 'status', 'version', 'created_at')
    list_filter = ('status', 'material_type', 'author')
    inlines = [MaterialRevisionInline]  # Show revisions on the material page


# Register the other models so they are visible in the admin
admin.site.register(Prompt)
admin.site.register(Assignment)
admin.site.register(Submission)


@admin.register(PlagiarismReport)
class PlagiarismReportAdmin(admin.ModelAdmin):
    """
    Määrittää PlagiarismReport-mallin hallintanäkymän.
    Näyttää plagiointiraportit listana, joka sisältää vastauksen,
    epäillyn lähteen, tuloksen ja luontiajan.
    Mahdollistaa hakuja submission id:n, opiskelijan käyttäjänimen
    ja lähteen id:n/käyttäjänimen perusteella.
    """
    list_display = ("submission", "suspected_source", "score", "created_at")
    search_fields = (
        "submission__id",
        "submission__student__username",
        "suspected_source__id",
        "suspected_source__student__username",
    )
    list_filter = ("created_at",)


class RubricCriterionInline(admin.TabularInline):
    """
    Määrittää RubricCriterion-mallin inline-esittämisen Rubric-muokkaussivulla.
    Mahdollistaa rubriikkikriteerien hallinnan suoraan rubriikkinäkymästä.
    """
    model = RubricCriterion
    extra = 1
    fields = ("name", "max_points", "guidance", "order")


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    """
    Määrittää Rubric-mallin hallintanäkymän.
    Näyttää rubriikit listana, joka sisältää otsikon, materiaalin,
    luojan ja luontiajan.
    Integroi RubricCriterion-inlinet ja tarjoaa hakutoiminnot
    otsikon, materiaalin otsikon ja luojan käyttäjänimen perusteella.
    """
    list_display = ("title", "material", "created_by", "created_at")
    inlines = [RubricCriterionInline]
    search_fields = ("title", "material__title", "created_by__username")


@admin.register(AIGrade)
class AIGradeAdmin(admin.ModelAdmin):
    """
    Määrittää AIGrade-mallin hallintanäkymän.
    Näyttää tekoälyn antamat arvosanat listana, joka sisältää
    vastauksen, rubriikin, käytetyn mallin nimen, kokonaispisteet,
    opettajan vahvistuksen tilan ja luontiajan.
    Tarjoaa hakutoimintoja ja suodatuksia.
    """
    list_display = (
        "submission",
        "rubric",
        "model_name",
        "total_points",
        "teacher_confirmed",
        "created_at",
    )
    search_fields = (
        "submission__id",
        "rubric__title",
        "submission__student__username",
    )
    list_filter = ("teacher_confirmed", "model_name", "created_at")