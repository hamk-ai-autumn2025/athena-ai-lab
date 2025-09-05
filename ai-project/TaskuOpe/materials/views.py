from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Material

@login_required(login_url='kirjaudu')  # named URL we’ll add below
def dashboard(request):
    user = request.user

    # Safety: if role is missing/unknown, punt to login
    role = getattr(user, "role", None)

    if role == "TEACHER":
        materials = (
            Material.objects
            .filter(author=user)
            .select_related("author")
            .order_by("-pk")  # change to '-created_at' if you have that field
        )
        return render(
            request,
            "materials/teacher_dashboard.html",
            {"materials": materials, "user": user}
        )

    elif role == "STUDENT":
        materials = (
            Material.objects
            .all()
            .select_related("author")
            .order_by("-pk")
        )
        return render(
            request,
            "materials/student_dashboard.html",
            {"materials": materials, "user": user}
        )

    # Unknown role → force re-auth (or customize as you like)
    return redirect("login")
