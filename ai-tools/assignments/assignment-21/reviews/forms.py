from django import forms
from .models import Book, Author

class BookForm(forms.ModelForm):
    author_name = forms.CharField(label="Kirjoittaja", max_length=120)

    class Meta:
        model = Book
        fields = ["title", "author_name", "published_year", "genre", "cover_url", "description"]

    def save(self, commit=True):
        name = self.cleaned_data.pop("author_name").strip()
        author, _ = Author.objects.get_or_create(name=name)
        book: Book = super().save(commit=False)
        book.author = author
        if commit:
            book.save()
        return book
