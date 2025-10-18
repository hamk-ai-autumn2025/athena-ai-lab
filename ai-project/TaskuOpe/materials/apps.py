from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
import os

class MaterialsConfig(AppConfig):
    """
    Konfiguraatioluokka 'materials'-sovellukselle.

    Määrittää sovelluksen perusasetukset, kuten automaattisen ensisijaisen avaimen tyypin,
    sovelluksen nimen ja ihmislukuisen nimen, joka näkyy esimerkiksi Django Adminissa.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "materials"
    verbose_name = _("Materiaalit")

    path = os.path.dirname(os.path.abspath(__file__))