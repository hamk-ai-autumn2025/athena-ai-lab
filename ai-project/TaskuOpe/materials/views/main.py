# materials/views/main.py

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .teacher import teacher_dashboard_view
from .student import student_dashboard_view

@login_required(login_url='kirjaudu')
def dashboard_view(request):
    """
    Ohjaa käyttäjän oikeaan dashboard-näkymään roolin perusteella.
    """
    user = request.user
    if user.role == 'TEACHER':
        return teacher_dashboard_view(request)
    elif user.role == 'STUDENT':
        return student_dashboard_view(request)
    return redirect('kirjaudu')