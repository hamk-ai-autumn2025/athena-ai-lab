# TaskuOpe/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "kirjaudu-ulos/",
        auth_views.LogoutView.as_view(next_page="kirjaudu"),  # ohjaa kirjautumissivulle
        name="kirjaudu_ulos",
    ),


    path(
        "kirjaudu/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="kirjaudu",
    ),

    # Sovelluksen päänäkymät
    path("", include("materials.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)