from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Import models from the correct apps
from .models import Material, Assignment
from users.models import CustomUser

# Import forms for this app
from .forms import AssignmentForm, MaterialForm

# --- Main Dashboard ---
@login_required
def dashboard_view(request):
    """
    Checks the user's role and renders the appropriate dashboard
    with the necessary data.
    """
    user = request.user
    
    if user.role == 'TEACHER':
        # Fetch all materials created by this teacher
        materials = Material.objects.filter(author=user)
        
        # Fetch all assignments given by this teacher, ordered by most recent
        assignments = Assignment.objects.filter(assigned_by=user).select_related('material', 'student').order_by('-created_at')
        
        context = {
            'materials': materials,
            'assignments': assignments,
        }
        return render(request, 'materials/teacher_dashboard.html', context)
    
    elif user.role == 'STUDENT':
        # Fetch all assignments given to this student
        assignments = Assignment.objects.filter(student=user).select_related('material', 'assigned_by')
        return render(request, 'materials/student_dashboard.html', {'assignments': assignments})
    
    else:
        # Fallback for users with no role
        return redirect('kirjaudu')

# --- Teacher's Workflow Views ---

@login_required
def create_material_view(request):
    """
    Handles the manual creation of a new Material object for testing.
    """
    if request.user.role != 'TEACHER':
        return redirect('dashboard')

    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save(commit=False)
            material.author = request.user
            material.status = Material.Status.DRAFT
            material.save()
            messages.success(request, f"Material '{material.title}' was created successfully.")
            return redirect('dashboard')
    else:
        form = MaterialForm()
    
    return render(request, 'materials/create_material.html', {'form': form})

@login_required
def material_detail_view(request, material_id):
    """
    Displays the full content of a single Material.
    """
    material = get_object_or_404(Material, id=material_id)
    
    # Security check: only the author can view the material
    if material.author != request.user:
        return redirect('dashboard') 

    return render(request, 'materials/material_detail.html', {'material': material})

@login_required
def assign_material_view(request, material_id):
    """
    Displays a form to assign a material to students and processes the submission.
    """
    material = get_object_or_404(Material, id=material_id)
    if material.author != request.user:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            selected_students = form.cleaned_data['students']
            due_at = form.cleaned_data['due_at']
            
            count = 0
            for student in selected_students:
                # get_or_create prevents creating duplicate assignments
                assignment, created = Assignment.objects.get_or_create(
                    material=material,
                    student=student,
                    defaults={
                        'assigned_by': request.user,
                        'due_at': due_at
                    }
                )
                if created:
                    count += 1
            
            messages.success(request, f"Material was successfully assigned to {count} student(s).")
            return redirect('dashboard')
    else:
        form = AssignmentForm()
            
    return render(request, 'materials/assign_material.html', {'form': form, 'material': material})