"""
Määrittelee 'users'-sovelluksen konfiguraation.

Tämä tiedosto sisältää sovelluksen asetukset, kuten sen nimen
ja oletusarvoisen automaattisen pääavaimen tyypin.
"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """
    Konfiguraatioluokka 'users'-sovellukselle.

    Määrittelee sovelluksen nimen ja oletusarvoisen kenttätyypin
    automaattisesti luoduille pääavaimille malleissa.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
