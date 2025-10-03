
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


from users.views import FinnishLoginView, simple_logout

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "kirjaudu-ulos/",
        simple_logout,
        name="kirjaudu_ulos",
    ),

    path(
        "kirjaudu/",
        FinnishLoginView.as_view(),
        name="kirjaudu",
    ),

    path("", include("materials.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)