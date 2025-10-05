# reviews/admin.py
from django.contrib import admin
from .models import Author, Book, Review

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title","author","published_year","genre")
    list_filter = ("author","published_year","genre")
    search_fields = ("title","author__name","genre")
    fields = ("title","author","published_year","genre","cover_url","description")

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("book","rating","reviewer","created_at")
    list_filter = ("rating","created_at")
    autocomplete_fields = ("book","reviewer")
    search_fields = ("book__title","reviewer__username","text")
