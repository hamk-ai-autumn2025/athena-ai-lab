from django.urls import path
from . import views
app_name = "reviews"
urlpatterns = [
    path("", views.BookListView.as_view(), name="book_list"),
    path("book/<int:pk>/", views.BookDetailView.as_view(), name="book_detail"),
    path("book/<int:pk>/review/", views.ReviewCreateView.as_view(), name="review_create"),
    path("book/new/", views.BookCreateView.as_view(), name="book_create"),
    path("review/<int:pk>/edit/",  views.ReviewUpdateView.as_view(), name="review_edit"),
    path("review/<int:pk>/delete/", views.ReviewDeleteView.as_view(), name="review_delete"),
    path("book/<int:pk>/edit/",   views.BookUpdateView.as_view(), name="book_edit"),
    path("book/<int:pk>/delete/", views.BookDeleteView.as_view(), name="book_delete"),
]
