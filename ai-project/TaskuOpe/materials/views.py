from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .ai_service import ask_llm
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.utils import timezone

# Import models from the correct apps
from .models import Material, Assignment, Submission
from users.models import CustomUser
from django.db import transaction
from django import forms


# Import forms for this app
from .forms import AssignmentForm, MaterialForm, SubmissionForm, GradingForm
from .forms import GradingForm  # varmista että tämä on lisätty forms.py:hin aiemmin


# --- Main Dashboard ---
@login_required(login_url='kirjaudu')
def dashboard_view(request):
    """
    Checks the user's role and renders the appropriate dashboard
    with the necessary data.
    """
    user = request.user
    
    if user.role == 'TEACHER':
        materials = Material.objects.filter(author=user)
        assignments = Assignment.objects.filter(assigned_by=user).select_related('material', 'student').order_by('-created_at')
        context = {
            'materials': materials,
            'assignments': assignments,
        }
        return render(request, 'materials/teacher_dashboard.html', context)
    
    elif user.role == 'STUDENT':
        assignments = Assignment.objects.filter(student=user).select_related('material', 'assigned_by')
        return render(request, 'materials/student_dashboard.html', {'assignments': assignments})
    
    else:
        return redirect('kirjaudu')

# --- Teacher's Workflow Views ---

@login_required
def create_material_view(request):
    """
    Manuaalinen materiaalin luonti + AI-testi samalla sivulla.
    """
    if request.user.role != 'TEACHER':
        return redirect('dashboard')

    ai_reply = None
    ai_prompt_val = ""

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'ai':
            ai_prompt_val = (request.POST.get('ai_prompt') or '').strip()
            if ai_prompt_val:
                ai_reply = ask_llm(ai_prompt_val, user_id=request.user.id)
            form = MaterialForm(request.POST or None)
            return render(request, 'materials/create_material.html', {'form': form, 'ai_prompt': ai_prompt_val, 'ai_reply': ai_reply})

        if action == 'save' or action is None:
            form = MaterialForm(request.POST)
            if form.is_valid():
                material = form.save(commit=False)
                material.author = request.user
                material.status = Material.Status.DRAFT
                material.save()
                messages.success(request, f"Material '{material.title}' was created successfully.")
                return redirect('dashboard')
            return render(request, 'materials/create_material.html', {
                'form': form,
                'ai_prompt': request.POST.get('ai_prompt', ''),
                'ai_reply': None,
            })

    form = MaterialForm()
    return render(request, 'materials/create_material.html', {
        'form': form,
        'ai_prompt': '',
        'ai_reply': None,
    })

@login_required
def material_detail_view(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    if material.author != request.user:
        return redirect('dashboard') 
    return render(request, 'materials/material_detail.html', {'material': material})

@login_required
def assign_material_view(request, material_id):
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
                assignment, created = Assignment.objects.get_or_create(
                    material=material,
                    student=student,
                    defaults={'assigned_by': request.user, 'due_at': due_at}
                )
                if created:
                    count += 1
            messages.success(request, f"Material was successfully assigned to {count} student(s).")
            return redirect('dashboard')
    else:
        form = AssignmentForm()
    return render(request, 'materials/assign_material.html', {'form': form, 'material': material})


# --- Students workflow view ---
@login_required
def assignment_detail_view(request, assignment_id):
    """
    Displays assignment, handles saving drafts, and processes final submissions.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if assignment.student != request.user:
        messages.error(request, "You are not authorized to view this assignment.")
        return redirect('dashboard')

    if assignment.status in [Assignment.Status.SUBMITTED, Assignment.Status.GRADED]:
        form = SubmissionForm()
        return render(request, 'materials/assignment_detail.html', {'assignment': assignment, 'form': form})

    if request.method == 'POST':
        form = SubmissionForm(request.POST)
        if 'save_draft' in request.POST:
            draft_text = request.POST.get('response', '')
            assignment.draft_response = draft_text
            assignment.status = Assignment.Status.IN_PROGRESS
            assignment.save()
            messages.info(request, "Luonnos tallennettu onnistuneesti!")
            return redirect('assignment_detail', assignment_id=assignment.id)

        elif 'submit_final' in request.POST:
            if form.is_valid():
                submission = form.save(commit=False)
                submission.student = request.user
                submission.assignment = assignment
                submission.save()
                assignment.status = Assignment.Status.SUBMITTED
                assignment.draft_response = ""
                assignment.save()
                messages.success(request, "Vastauksesi on lähetetty onnistuneesti!")
                return redirect('dashboard')
    
    else:
        form = SubmissionForm(initial={'response': assignment.draft_response})

    context = {
        'assignment': assignment,
        'form': form,
    }
    return render(request, 'materials/assignment_detail.html', context)
    
# --- Deletion Views ---
@login_required
def delete_material_view(request, material_id):
    material = get_object_or_404(Material, id=material_id, author=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    title = material.title
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

@login_required(login_url='kirjaudu')
def view_submissions(request, material_id):
    """
    Opettaja: listaa tietyn materiaalin palautukset/arvioinnit.
    Turva: vain materiaalin tekijä näkee.
    """
    material = get_object_or_404(Material, id=material_id)
    if getattr(request.user, "role", None) != "TEACHER" or material.author_id != request.user.id:
        messages.error(request, "Sinulla ei ole oikeuksia tarkastella tätä sivua.")
        return redirect('dashboard')

    assignments = (
        Assignment.objects
        .select_related('student', 'material')
        .filter(material=material, status__in=[Assignment.Status.SUBMITTED, Assignment.Status.GRADED])
        .order_by('-created_at')
    )

    return render(request, 'materials/view_submissions.html', {
        'material': material,
        'assignments': assignments,
    })


@login_required(login_url='kirjaudu')
@transaction.atomic
def grade_submission_view(request, submission_id):
    """
    Opettaja arvioi yksittäisen palautuksen.
    """
    submission = get_object_or_404(
        Submission.objects.select_related('assignment__student', 'assignment__material'),
        id=submission_id
    )
    assignment = submission.assignment
    material = assignment.material

    # Turvatarkistus: vain materiaalin tekijä (opettaja) saa arvioida
    if getattr(request.user, "role", None) != "TEACHER" or material.author_id != request.user.id:
        messages.error(request, "Sinulla ei ole oikeuksia arvioida tätä palautusta.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = GradingForm(request.POST, instance=submission)
        if form.is_valid():
            sub = form.save(commit=False)         # ota instanssi muokattavaksi
            sub.graded_at = timezone.now()        # leimaa arviointihetki
            sub.save()                            # tallenna arvosana/pisteet/palaute

            assignment.status = Assignment.Status.GRADED
            assignment.save(update_fields=['status'])

            messages.success(request, "Arviointi tallennettu.")
            return redirect('view_submissions', material_id=material.id)
    else:
        form = GradingForm(instance=submission)

    return render(request, 'materials/grade_submission.html', {
        'material': material,
        'assignment': assignment,
        'submission': submission,
        'form': form,
    })
