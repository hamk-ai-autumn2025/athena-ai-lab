from django.db import models
from django.conf import settings # To link to our CustomUser model

class Material(models.Model):
    """
    Represents a piece of educational material created by a teacher.
    """
    # We can define choices for the material type
    class MaterialType(models.TextChoices):
        QUIZ = 'QUIZ', 'Quiz'
        GAME = 'GAME', 'Game'
        IMAGE = 'IMAGE', 'Image'
        VIDEO = 'VIDEO', 'Video'

    title = models.CharField(max_length=200)
    content = models.TextField(help_text="The main content, or a description for the material.")
    material_type = models.CharField(max_length=50, choices=MaterialType.choices)
    
    # This links the material to the user who created it.
    # We limit choices to only users with the 'TEACHER' role.
    # The on_delete=models.CASCADE means if a teacher is deleted, their materials are also deleted.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'TEACHER'},
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title