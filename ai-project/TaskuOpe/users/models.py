"""
Määrittelee sovelluksen mukautetun käyttäjämallin.

Tässä tiedostossa laajennetaan Djangon oletusarvoista User-mallia
lisäämällä sille rooli- ja luokka-aste-kentät.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Mukautettu käyttäjämalli, joka laajentaa Djangon AbstractUseria.

    AbstractUser sisältää jo peruskäyttäjätiedot, kuten käyttäjätunnuksen,
    sähköpostin, salasanan, etunimen, sukunimen jne. Tähän malliin
    lisätään 'role' (rooli) ja 'grade_class' (luokka-aste) -kentät.
    """
    # We define choices for the user roles
    class Role(models.TextChoices):
        """
        Määrittelee käyttäjän roolivaihtoehdot.

        TextChoices on kätevä tapa määritellä tekstipohjaisia valintoja,
        jotka tarjoavat sekä tietokantaan tallennettavan arvon (esim. 'TEACHER')
        että ihmiselle luettavan selitteen (esim. 'Teacher').
        """
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'

    # This is the new field we are adding
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.STUDENT)

    grade_class = models.PositiveSmallIntegerField(
        verbose_name="Luokka-aste",
        null=True,  # Salli tyhjä arvo (esim. opettajat)
        blank=True, # Ei pakollinen lomakkeissa
        choices=[(i, f"{i}. luokka") for i in range(1, 7)] # Valinnat 1-6
    )

   # __str__-metodin lisääminen parantaa mallin esitystä Djangon hallintapaneelissa
    # ja muissa paikoissa, joissa objekti muutetaan merkkijonoksi.
    def __str__(self):
        """Palauttaa käyttäjän käyttäjätunnuksen merkkijonoesityksenä."""
        return self.username
   