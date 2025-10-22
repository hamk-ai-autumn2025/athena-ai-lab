# TaskuOpe/TaskuOpe/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import FinnishLoginView, simple_logout
# Tuo dashboard-näkymä materials-sovelluksesta
from materials.views import main as materials_main_views # Tai mistä dashboard_view tuleekaan

urlpatterns = [
    path("admin/", admin.site.urls),
    path("kirjaudu-ulos/", simple_logout, name="kirjaudu_ulos"),
    path("kirjaudu/", FinnishLoginView.as_view(), name="kirjaudu"),

    # Asetetaan dashboard juuripolkuun
    path("", materials_main_views.dashboard_view, name="dashboard"),

    # Sisällytetään materials-sovelluksen URLit esim. /app/-polun alle
    # TAI voit sisällyttää sen ilman polkua, jos materials/urls.py:ssä ei ole ristiriitoja
    path("", include("materials.urls")), # Kokeile tätä ensin, jos dashboard on ainoa juuripolku materialsissa

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)