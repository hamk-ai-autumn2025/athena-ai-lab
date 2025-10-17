# users/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Mukautettu käyttäjämalli, joka laajentaa Djangon AbstractUseria.
    """
    class Role(models.TextChoices):
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'

    role = models.CharField(max_length=50, choices=Role.choices, default=Role.STUDENT)

    grade_class = models.PositiveSmallIntegerField(
        verbose_name="Luokka-aste",
        null=True,
        blank=True,
        choices=[(i, f"{i}. luokka") for i in range(1, 7)]
    )

    profile_image = models.ImageField(
        verbose_name="Profiilikuva",
        upload_to='profile_pics/',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.username