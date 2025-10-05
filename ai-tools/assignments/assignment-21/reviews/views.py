# reviews/views.py
from django.views.generic import ListView, DetailView, CreateView
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Book, Review
from .forms import BookForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from .forms import BookForm

class BookListView(ListView):
    model = Book
    template_name = "reviews/book_list.html"
    context_object_name = "books"
    paginate_by = 12
    

    def get_queryset(self):
        qs = Book.objects.select_related("author").annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews"),
        )
        q = self.request.GET.get("q", "").strip()
        author = self.request.GET.get("author", "").strip()
        g = self.request.GET.get("genre", "").strip()
        y_from = self.request.GET.get("y_from") or ""
        y_to = self.request.GET.get("y_to") or ""
        minr = self.request.GET.get("minr") or ""
        sort = self.request.GET.get("sort", "rating")

        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(author__name__icontains=q))
        if author:
            qs = qs.filter(author__name__icontains=author)
        if g:
            qs = qs.filter(genre__icontains=g)
        if y_from.isdigit():
            qs = qs.filter(published_year__gte=int(y_from))
        if y_to.isdigit():
            qs = qs.filter(published_year__lte=int(y_to))
        if minr.isdigit():
            qs = qs.filter(reviews__rating__gte=int(minr)).distinct()

        if sort == "newest":
            qs = qs.order_by("-published_year", "title")
        elif sort == "title":
            qs = qs.order_by("title")
        elif sort == "reviews":
            qs = qs.order_by("-review_count", "title")
        else:  # rating (default)
            qs = qs.order_by("-avg_rating", "-review_count", "title")
        return qs

def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    # säilytä syötteet kentissä
    ctx.update({k: self.request.GET.get(k, "") for k in ["q","author","genre","y_from","y_to","minr","sort"]})
    # täyttöehdotukset lisäsuodattimiin
    ctx["author_suggestions"] = (
        Book.objects.values_list("author__name", flat=True).distinct().order_by("author__name")
    )
    ctx["genre_suggestions"] = (
        Book.objects.exclude(genre="").values_list("genre", flat=True).distinct().order_by("genre")
    )
    return ctx

class BookDetailView(DetailView):
    model = Book
    template_name = "reviews/book_detail.html"
    context_object_name = "book"
    def get_queryset(self):
        return Book.objects.select_related("author").annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews"),
        )

class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    fields = ["rating", "text"]
    template_name = "reviews/review_form.html"
    def form_valid(self, form):
        book = get_object_or_404(Book, pk=self.kwargs["pk"])
        form.instance.book = book
        form.instance.reviewer = self.request.user
        messages.success(self.request, "Arvostelu tallennettu ✅")
        return super().form_valid(form)
    def get_success_url(self):
        return reverse("reviews:book_detail", args=[self.kwargs["pk"]])
    
# ---- TÄMÄ LUOKKA OLI RIKKI SISENNYKSEN TAKIA ----
class BookCreateView(LoginRequiredMixin, CreateView):
    form_class = BookForm
    template_name = "reviews/book_form.html"

    def get_success_url(self):
        messages.success(self.request, "Kirja lisätty ✅")
        return reverse("reviews:book_detail", args=[self.object.pk])
    

 # --- Staff-vaatimus mixin ---
class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

# --- ARVOSTELUN MUOKKAUS (vain staff) ---
class ReviewUpdateView(StaffRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Review
    fields = ["rating", "text"]
    template_name = "reviews/review_form.html"  # sama lomake käy
    context_object_name = "review"

    def get_success_url(self):
        return reverse("reviews:book_detail", args=[self.object.book_id])

# --- ARVOSTELUN POISTO (vain staff) ---
class ReviewDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Review
    template_name = "reviews/review_confirm_delete.html"
    context_object_name = "review"

    def get_success_url(self):
        return reverse("reviews:book_detail", args=[self.object.book_id])
    
# --- KIRJAN MUOKKAUS (vain staff) ---
class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

class BookUpdateView(StaffRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "reviews/book_form.html"
    def get_success_url(self):
        messages.success(self.request, "Kirja päivitetty ✅")
        return reverse("reviews:book_detail", args=[self.object.pk])

class BookDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Book
    template_name = "reviews/book_confirm_delete.html"
    def get_success_url(self):
        messages.success(self.request, "Kirja poistettu 🗑️")
        return reverse("reviews:book_list")


