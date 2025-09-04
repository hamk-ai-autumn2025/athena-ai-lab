from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Extends the default User model.
    The AbstractUser model already includes fields like username,
    email, password, first_name, last_name, etc.
    """
    # We define choices for the user roles
    class Role(models.TextChoices):
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'

    # This is the new field we are adding
    role = models.CharField(max_length=50, choices=Role.choices)