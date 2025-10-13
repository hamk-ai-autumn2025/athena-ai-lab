"""
Määrittelee projektin pää-URL-reitityksen.

Tämä moduuli sisältää URL-polut Django-hallinnolle, käyttäjän
sisään- ja uloskirjautumiselle sekä muiden sovellusten, kuten
'materials', URL-reititysten sisällyttämiselle.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Tuodaan näkymät, joita käytetään suoraan tässä URL-konfiguraatiossa.
from users.views import FinnishLoginView, simple_logout

urlpatterns = [
    # Hallintapaneelin URL-polku
    path("admin/", admin.site.urls),

    # Uloskirjautumis-URL
    # Käyttää 'simple_logout'-näkymää käyttäjän uloskirjaamiseen.
    path(
        "kirjaudu-ulos/",
        simple_logout,
        name="kirjaudu_ulos",
    ),

    # Sisäänkirjautumis-URL
    # Käyttää FinnishLoginView:ta sisäänkirjautumissivuna.
    path(
        "kirjaudu/",
        FinnishLoginView.as_view(),
        name="kirjaudu",
    ),

    # Sisällyttää 'materials'-sovelluksen URL-reititykset.
    # Kaikki polut, jotka eivät vastaa edellisiä, ohjataan 'materials'-sovellukselle.
    path("", include("materials.urls")),
]

# Kehitysympäristön tiedostojen tarjoilu
# Jos DEBUG-tila on päällä, lisätään URL-kaavoihin reitit
# median (esim. käyttäjien lataamien kuvien) tarjoiluun.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)