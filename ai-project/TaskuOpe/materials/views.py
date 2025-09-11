from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .ai_service import ask_llm #lisäys AI-kyselyä varten
from django.http import HttpResponseForbidden, HttpResponseNotAllowed

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

# BEGIN disabled 2025-09-11: korvattu AI-paneelin versiolla
# @login_required
# def create_material_view(request):
#     """
#     Handles the manual creation of a new Material object for testing.
#     """
#     if request.user.role != 'TEACHER':
#         return redirect('dashboard')
#
#     if request.method == 'POST':
#         form = MaterialForm(request.POST)
#         if form.is_valid():
#             material = form.save(commit=False)
#             material.author = request.user
#             material.status = Material.Status.DRAFT
#             material.save()
#             messages.success(request, f"Material '{material.title}' was created successfully.")
#             return redirect('dashboard')
#     else:
#         form = MaterialForm()
#
#     return render(request, 'materials/create_material.html', {'form': form})
# END disabled 2025-09-11

#uusi näkymä AI-kyselyä varten

@login_required
def create_material_view(request):
    """
    Manuaalinen materiaalin luonti + AI-testi samalla sivulla.
    AI-testi EI tallenna eikä täytä kenttiä automaattisesti.
    """
    if request.user.role != 'TEACHER':
        return redirect('dashboard')

    ai_reply = None
    ai_prompt_val = ""

    if request.method == 'POST':
        action = request.POST.get('action')

        # --- AI-kysely (ei tallennusta) ---
        if action == 'ai':
            ai_prompt_val = (request.POST.get('ai_prompt') or '').strip()
            if ai_prompt_val:
                ai_reply = ask_llm(ai_prompt_val, user_id=request.user.id)
            # Palauta sivu käyttäjän syötteillä
            form = MaterialForm(request.POST or None)
            return render(request, 'materials/create_material.html', {
                'form': form,
                'ai_prompt': ai_prompt_val,
                'ai_reply': ai_reply,
            })

        # --- Normaali tallennus ---
        if action == 'save' or action is None:
            form = MaterialForm(request.POST)
            if form.is_valid():
                material = form.save(commit=False)
                material.author = request.user
                material.status = Material.Status.DRAFT
                material.save()
                messages.success(request, f"Material '{material.title}' was created successfully.")
                return redirect('dashboard')
            # validointivirhe
            return render(request, 'materials/create_material.html', {
                'form': form,
                'ai_prompt': request.POST.get('ai_prompt', ''),
                'ai_reply': None,
            })

    # GET
    form = MaterialForm()
    return render(request, 'materials/create_material.html', {
        'form': form,
        'ai_prompt': '',
        'ai_reply': None,
    })

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

# --- Deletion Views ---
@login_required
def delete_material_view(request, material_id):
    material = get_object_or_404(Material, id=material_id, author=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    title = material.title
    # Jos Assignment FK on on_delete=CASCADE, tämä riittää:
    material.delete()
    messages.success(request, f"Materiaali '{title}' poistettu.")
    return redirect('dashboard')

@login_required
def delete_assignment_view(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, assigned_by=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    assignment.delete()
    messages.success(request, "Tehtävänanto poistettu.")
    return redirect('dashboard')