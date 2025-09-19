import pytest
from django.urls import reverse
from django.utils import timezone
from users.models import CustomUser
from materials.models import Material, Assignment

@pytest.mark.django_db
def test_student_sees_own_assignments(client):
    student = CustomUser.objects.create_user(username="opiskelija", password="x", role="STUDENT")
    teacher = CustomUser.objects.create_user(username="ope", password="x", role="TEACHER")
    material = Material.objects.create(title="Testi", content="...", author=teacher)
    a = Assignment.objects.create(material=material, student=student, assigned_by=teacher, due_at=timezone.now())

    client.login(username="opiskelija", password="x")
    resp = client.get(reverse("student_assignments"))
    assert resp.status_code == 200
    assert b"Testi" in resp.content
