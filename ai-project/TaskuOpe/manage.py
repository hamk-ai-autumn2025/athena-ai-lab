#!/usr/bin/env python
"""
Djangon komentorivin apuohjelma hallinnollisiin tehtäviin.

Tämä tiedosto on Djangon projektin pääsisäänkäyntipiste,
jota käytetään erilaisten hallinnollisten komentojen, kuten
palvelimen käynnistämiseen, tietokannan migraatioihin tai
uusien sovellusten luomiseen.
"""
import os
import sys


def main():
    """
    Suorittaa Djangon hallinnolliset tehtävät.

    Asettaa ympäristömuuttujan `DJANGO_SETTINGS_MODULE` osoittamaan
    projektin asetustiedostoon ja kutsuu Djangon komentorivityökalua
    argumenteilla, jotka on annettu komennolle.
    """

    # Asettaa 'DJANGO_SETTINGS_MODULE' ympäristömuuttujan.
    # Tämä kertoo Djangolle, mikä asetustiedosto (.settings) on käytössä.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TaskuOpe.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # Suorittaa Djangon komennon komentoriviltä saaduilla argumenteilla
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
