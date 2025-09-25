from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.utils import timezone
from django.db import transaction
from django import forms
from django.core.paginator import Paginator
from django.db.models import Q
import csv
from django.http import HttpResponse

# AI-avustin (demo/tuotanto)
from .ai_service import ask_llm
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# 👉 Plagiointitarkistuspalvelu (UUSI)
from .plagiarism import build_or_update_report

# Import models and forms
from .models import Material, Assignment, Submission
from users.models import CustomUser
from .forms import AssignmentForm, MaterialForm, SubmissionForm, GradingForm


# --- Main Dashboard ---
@login_required(login_url='kirjaudu')
def dashboard_view(request):
    """Renders the correct dashboard based on user role."""
    user = request.user

    if user.role == 'TEACHER':
        materials = Material.objects.filter(author=user)
        assignments = (
            Assignment.objects
            .filter(assigned_by=user)
            .select_related('material', 'student')
            .order_by('-created_at')
        )
        context = {'materials': materials, 'assignments': assignments}
        return render(request, 'dashboard/teacher.html', context)

    elif user.role == 'STUDENT':
        qs = (
            Assignment.objects
            .select_related('material', 'assigned_by')
            .filter(student=user)
        )

        counts = {
            "assigned": qs.filter(status=Assignment.Status.ASSIGNED).count(),
            "in_progress": qs.filter(status=Assignment.Status.IN_PROGRESS).count(),
            "graded": qs.filter(status=Assignment.Status.GRADED).count(),
        }

        due_soon = (
            qs.exclude(due_at__isnull=True)
              .filter(due_at__gte=timezone.now())
              .order_by('due_at')[:3]
        )

        return render(request, 'dashboard/student.html', {
            "counts": counts,
            "due_soon": due_soon,
        })

    return redirect('kirjaudu')


# --- Student views ---
@login_required(login_url='kirjaudu')
def student_assignments_view(request):
    user = request.user
    if user.role != 'STUDENT':
        return redirect('dashboard')

    qs = (Assignment.objects
          .select_related('material', 'assigned_by')
          .filter(student=user))

    status = request.GET.get('status') or ""
    order = request.GET.get('order') or "due_at"

    if status:
        qs = qs.filter(status=status)

    if order:
        qs = qs.order_by(order)

    ctx = {
        "assigned": qs.filter(status="ASSIGNED"),
        "in_progress": qs.filter(status="IN_PROGRESS"),
        "submitted": qs.filter(status__in=["SUBMITTED", "GRADED"]),
        "status": status,
        "order": order,
        "now": timezone.now(), 
    }
    return render(request, 'student/assignments.html', ctx)


@login_required(login_url='kirjaudu')
def student_grades_view(request):
    """
    Oppilaan palautukset & arvioinnit:
    - Näytetään SUBMITTED ja GRADED
    - Haku materiaalin nimellä/opettajan nimellä
    - Sivutus
    """
    if request.user.role != 'STUDENT':
        return redirect('dashboard')

    q = (request.GET.get('q') or '').strip()

    qs = (Assignment.objects
          .select_related('material', 'assigned_by')
          .filter(student=request.user, status__in=['SUBMITTED', 'GRADED'])
          .order_by('-created_at'))

    if q:
        qs = qs.filter(
            Q(material__title__icontains=q) |
            Q(assigned_by__first_name__icontains=q) |
            Q(assigned_by__last_name__icontains=q) |
            Q(assigned_by__username__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'student/grades.html', {
        'assignments': page_obj,
        'q': q,
        'page_obj': page_obj,
        'now': timezone.now(),
    })

# --- Materials ---
@login_required(login_url='kirjaudu')
def material_list_view(request):
    """Lists all materials created by the teacher."""
    if request.user.role != 'TEACHER':
        messages.error(request, "Vain opettajat voivat nähdä tämän sivun.")
        return redirect('dashboard')

    materials = Material.objects.filter(author=request.user)
    return render(request, 'materials/list.html', {'materials': materials})


@login_required(login_url='kirjaudu')
def create_material_view(request):
    """Manual material creation + AI helper."""
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
            return render(request, 'materials/create.html', {
                'form': form,
                'ai_prompt': ai_prompt_val,
                'ai_reply': ai_reply
            })

        if action == 'save' or action is None:
            form = MaterialForm(request.POST)
            if form.is_valid():
                material = form.save(commit=False)
                material.author = request.user
                material.status = Material.Status.DRAFT
                material.save()
                messages.success(request, f"Material '{material.title}' was created successfully.")
                return redirect('dashboard')
            return render(request, 'materials/create.html', {
                'form': form,
                'ai_prompt': request.POST.get('ai_prompt', ''),
                'ai_reply': None
            })

    form = MaterialForm()
    return render(request, 'materials/create.html', {'form': form, 'ai_prompt': '', 'ai_reply': None})


@login_required(login_url='kirjaudu')
def material_detail_view(request, material_id):
    """Shows material details for the teacher."""
    material = get_object_or_404(Material, id=material_id)
    if material.author != request.user:
        return redirect('dashboard')
    return render(request, 'materials/detail.html', {'material': material})


# --- Assignments ---
@login_required(login_url='kirjaudu')
def assign_material_view(request, material_id):
    """Assign material to students."""
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
    return render(request, 'assignments/assign.html', {'form': form, 'material': material})


@login_required(login_url='kirjaudu')
def assignment_detail_view(request, assignment_id):
    """
    Oppilas: katso tehtävä, tallenna luonnos, tai lähetä lopullinen vastaus.
    - Jos tehtävä on jo SUBMITTED/GRADED -> renderöidään lukutilassa (ei muokkausta).
    - Muuten: voidaan tallentaa luonnos tai lähettää lopullinen.
    """
    assignment = get_object_or_404(
        Assignment.objects.select_related('material', 'student', 'assigned_by'),
        id=assignment_id
    )

    # Oikeustarkistus
    if assignment.student_id != request.user.id:
        messages.error(request, "You are not authorized to view this assignment.")
        return redirect('dashboard')

    # Jos jo palautettu/arvioitu: näytä lukutilassa (ei muokkauslomaketta)
    if assignment.status in (Assignment.Status.SUBMITTED, Assignment.Status.GRADED):
        # Tyhjä form vain template-yhteensopivuuden vuoksi
        form = SubmissionForm()
        return render(request, 'assignments/detail.html', {
            'assignment': assignment,
            'form': form,
            'readonly': True,          # <-- voit käyttää templaatissa estämään editoinnin
            'now': timezone.now(),     # <-- hyödyllinen esim. eräpäiväbadgeihin
        })

    # Muokkaustila
    if request.method == 'POST':
        form = SubmissionForm(request.POST)

        # Luonnoksen tallennus (manuaalinen nappi)
        if 'save_draft' in request.POST:
            assignment.draft_response = request.POST.get('response', '').strip()
            # Jos jotain sisältöä -> siirrä tilaan IN_PROGRESS
            if assignment.draft_response and assignment.status == Assignment.Status.ASSIGNED:
                assignment.status = Assignment.Status.IN_PROGRESS
            assignment.save(update_fields=['draft_response', 'status'])
            messages.info(request, "Luonnos tallennettu onnistuneesti!")
            return redirect('assignment_detail', assignment_id=assignment.id)

        # Lopullinen lähetys
        elif 'submit_final' in request.POST:
            if form.is_valid():
                submission = form.save(commit=False)
                submission.student = request.user
                submission.assignment = assignment

                # Jos Submission-mallissa on nämä kentät, asetetaan selkeästi
                if hasattr(submission, 'status'):
                    submission.status = Submission.Status.SUBMITTED
                if hasattr(submission, 'submitted_at'):
                    submission.submitted_at = timezone.now()

                submission.save()

                assignment.status = Assignment.Status.SUBMITTED
                assignment.draft_response = ""
                assignment.save(update_fields=['status', 'draft_response'])

                messages.success(request, "Vastauksesi on lähetetty onnistuneesti!")
                return redirect('dashboard')

    else:
        # Esitäytä lomake mahdollisella luonnoksella
        form = SubmissionForm(initial={'response': assignment.draft_response})

    return render(request, 'assignments/detail.html', {
        'assignment': assignment,
        'form': form,
        'readonly': False,
        'now': timezone.now(),
    })

@login_required(login_url='kirjaudu')
@require_POST
def assignment_autosave_view(request, assignment_id):
    """
    Tallentaa luonnoksen taustalla (AJAX). Palauttaa JSONin.
    Käytä tätä fetch()-kutsulla assignments/detail.html -sivulla.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Oikeustarkistus: vain omaan tehtävään
    if assignment.student_id != request.user.id:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    # Jos tehtävä jo SUBMITTED/GRADED, ei enää autosavea
    if assignment.status in (Assignment.Status.SUBMITTED, Assignment.Status.GRADED):
        return JsonResponse({"ok": False, "error": "locked"}, status=400)

    draft = (request.POST.get("response") or "").strip()
    assignment.draft_response = draft

    # Jos oli "ASSIGNED" ja nyt tuli sisältöä -> vaihda "IN_PROGRESS"
    if draft and assignment.status == Assignment.Status.ASSIGNED:
        assignment.status = Assignment.Status.IN_PROGRESS

    assignment.save(update_fields=["draft_response", "status"])

    return JsonResponse({"ok": True, "saved_at": timezone.now().isoformat()})


# --- Submissions & Grading ---
@login_required(login_url='kirjaudu')
def view_submissions(request, material_id):
    """Teacher: view all student submissions for a material."""
    material = get_object_or_404(Material, id=material_id)
    if request.user.role != "TEACHER" or material.author_id != request.user.id:
        messages.error(request, "Sinulla ei ole oikeuksia tarkastella tätä sivua.")
        return redirect('dashboard')

    assignments = (
        Assignment.objects
        .select_related('student', 'material')
        .filter(material=material, status__in=[Assignment.Status.SUBMITTED, Assignment.Status.GRADED])
        .order_by('-created_at')
    )

    return render(request, 'assignments/student_submissions.html', {
        'material': material,
        'assignments': assignments
    })


@login_required(login_url='kirjaudu')
@transaction.atomic
def grade_submission_view(request, submission_id):
    """Teacher: grade a single student submission."""
    submission = get_object_or_404(
        Submission.objects.select_related('assignment__student', 'assignment__material'),
        id=submission_id
    )
    assignment = submission.assignment
    material = assignment.material

    if request.user.role != "TEACHER" or material.author_id != request.user.id:
        messages.error(request, "Sinulla ei ole oikeuksia arvioida tätä palautusta.")
        return redirect('dashboard')

    # 👉 Plagiointitarkistus napista (ei automaattisesti)
    if request.method == 'POST' and 'run_plagiarism' in request.POST:
        try:
            report = build_or_update_report(submission)
            if report.suspected_source:
                messages.success(
                    request,
                    f"Alkuperäisyysraportti päivitetty. Samankaltaisuus: {report.score:.2f}"
                )
            else:
                messages.info(
                    request,
                    "Raportti päivitetty. Merkittävää samankaltaisuutta ei löytynyt."
                )
        except Exception as e:
            messages.error(request, f"Raportin luonti epäonnistui: {e}")
        # Redirect, jotta POST ei toistu (PRG-malli)
        return redirect('grade_submission', submission_id=submission.id)

    if request.method == 'POST':
        form = GradingForm(request.POST, instance=submission)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.graded_at = timezone.now()
            sub.save()

            assignment.status = Assignment.Status.GRADED
            assignment.save(update_fields=['status'])

            messages.success(request, "Arviointi tallennettu.")
            return redirect('view_submissions', material_id=material.id)
    else:
        form = GradingForm(instance=submission)

    # Viedään mahdollinen raportti templaatille
    plagiarism_report = getattr(submission, "plagiarism_report", None)

    return render(request, 'assignments/grade.html', {
        'material': material,
        'assignment': assignment,
        'submission': submission,
        'form': form,
        'plagiarism_report': plagiarism_report,  # <-- käytä templaatissa
    })


@login_required(login_url='kirjaudu')
def view_all_submissions_view(request):
    if request.user.role != 'TEACHER':
        messages.error(request, "Vain opettajat voivat nähdä tämän sivun.")
        return redirect('dashboard')

    q = (request.GET.get("q") or "").strip()
    st = request.GET.get("status")  # SUBMITTED | GRADED | None

    base = (Assignment.objects
            .filter(assigned_by=request.user)
            .select_related('material', 'student')
            .order_by('-created_at'))

    if st in ("SUBMITTED", "GRADED"):
        base = base.filter(status=st)

    if q:
        base = base.filter(
            Q(material__title__icontains=q) |
            Q(student__username__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__last_name__icontains=q)
        )

    page = Paginator(base, 20).get_page(request.GET.get("page"))
    return render(request, 'assignments/submissions_list.html', {
        'assignments': page,  # paginator page object
        'q': q,
        'status': st or "",
    })

# --- Deletion ---
@login_required(login_url='kirjaudu')
def delete_material_view(request, material_id):
    material = get_object_or_404(Material, id=material_id, author=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    title = material.title
    material.delete()
    messages.success(request, f"Materiaali '{title}' poistettu.")
    return redirect('dashboard')


@login_required(login_url='kirjaudu')
def delete_assignment_view(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, assigned_by=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    assignment.delete()
    messages.success(request, "Tehtävänanto poistettu.")
    return redirect('dashboard')

@login_required(login_url='kirjaudu')
def export_submissions_csv_view(request):
    if request.user.role != 'TEACHER':
        messages.error(request, "Vain opettajat voivat viedä palautuksia.")
        return redirect('dashboard')

    q = (request.GET.get("q") or "").strip()
    st = request.GET.get("status")

    qs = (Assignment.objects
          .filter(assigned_by=request.user)
          .select_related('material', 'student')
          .order_by('-created_at'))

    if st in ("SUBMITTED", "GRADED"):
        qs = qs.filter(status=st)

    if q:
        qs = qs.filter(
            Q(material__title__icontains=q) |
            Q(student__username__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__last_name__icontains=q)
        )

    # HTTP response with CSV headers
    now_str = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"palautukset_{now_str}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Oppilas",
        "Käyttäjätunnus",
        "Materiaali",
        "Määräaika",
        "Tila",
        "Palautettu (viimeisin)",
        "Pisteet",
        "Max pisteet",
        "Arvosana",
        "Palaute (lyhyt)"
    ])

    for a in qs:
        sub = a.submissions.last()
        student_name = (a.student.get_full_name() or "").strip() or a.student.username
        submitted_at = sub.submitted_at.strftime("%d.%m.%Y %H:%M") if getattr(sub, "submitted_at", None) else ""
        score = getattr(sub, "score", None)
        max_score = getattr(sub, "max_score", None)
        grade = getattr(sub, "grade", "")
        feedback = (getattr(sub, "feedback", "") or "").replace("\n", " ").strip()
        if len(feedback) > 120:
            feedback = feedback[:117] + "..."

        writer.writerow([
            student_name,
            a.student.username,
            a.material.title,
            a.due_at.strftime("%d.%m.%Y %H:%M") if a.due_at else "",
            a.get_status_display(),
            submitted_at,
            "" if score is None else score,
            "" if max_score is None else max_score,
            grade,
            feedback,
        ])

    return response
