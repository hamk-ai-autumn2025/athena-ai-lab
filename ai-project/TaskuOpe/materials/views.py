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
from .models import Assignment
from django.core.files.storage import FileSystemStorage
import io, os, json, base64, uuid, datetime
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

# AI-avustin (demo/tuotanto)
from .ai_service import ask_llm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

# 👉 Plagiointitarkistuspalvelu (UUSI)
from .plagiarism import build_or_update_report
from .forms import AssignForm

# Import models and forms
from .models import Material, Assignment, Submission
from users.models import CustomUser
from .forms import AssignmentForm, MaterialForm, SubmissionForm, GradingForm

# Rubric & AI grading -> arviointikriteeristö & AI-arviointi
from .models import AIGrade, Rubric
from .ai_rubric import create_or_update_ai_grade

from urllib.parse import urljoin
from django.core.files.base import ContentFile
from .forms import AddImageForm
from .models import MaterialImage

#Kuvageneraation importteja
import markdown as md
import re
from django.utils.safestring import mark_safe

from .ai_service import generate_image_bytes

from django.core.files.base import ContentFile
from .forms import AddImageForm
from .models import MaterialImage
import re
from django.utils.safestring import mark_safe

try:
    from openai import OpenAI
    _has_openai = True
except Exception:
    _has_openai = False

# materials/views.py
import markdown as md
from django.utils.safestring import mark_safe
from django.shortcuts import render, get_object_or_404

# materials/views.py
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from .models import MaterialImage

# views.py
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io

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

    content_html = render_material_content_to_html(material.content)

    return render(request, 'materials/detail.html', {
        'material': material,
        'content_html': content_html,
    })


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
    return render(request, "assignments/assign.html", {"material": m, "form": form})


@login_required(login_url='kirjaudu')
def assignment_detail_view(request, assignment_id):
    """
    Oppilas: katso tehtävä, tallenna luonnos, tai lähetä lopullinen vastaus.
    """
    assignment = get_object_or_404(
        Assignment.objects.select_related('material', 'student', 'assigned_by'),
        id=assignment_id
    )

    # Oikeustarkistus
    if assignment.student_id != request.user.id:
        messages.error(request, "You are not authorized to view this assignment.")
        return redirect('dashboard')

    # RENDERÖITY MATERIAALISISÄLTÖ (kuvat ym. näkyviin oppilaalle)
    content_html = render_material_content_to_html(assignment.material.content)

    # Jos jo palautettu/arvioitu: näytä lukutilassa
    if assignment.status in (Assignment.Status.SUBMITTED, Assignment.Status.GRADED):
        form = SubmissionForm()
        last_sub = assignment.submissions.last()
        ai_grade = getattr(last_sub, 'ai_grade', None) if last_sub else None

        return render(request, 'assignments/detail.html', {
            'assignment': assignment,
            'form': form,
            'readonly': True,
            'now': timezone.now(),
            'ai_grade': ai_grade,
            'content_html': content_html,   # <-- tärkeä lisä
        })

    # Muokkaustila
    if request.method == 'POST':
        form = SubmissionForm(request.POST)

        # Luonnoksen tallennus
        if 'save_draft' in request.POST:
            assignment.draft_response = request.POST.get('response', '').strip()
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
        # Esitäytä lomake luonnoksella
        form = SubmissionForm(initial={'response': assignment.draft_response})

    # Muokkausnäkymä
    return render(request, 'assignments/detail.html', {
        'assignment': assignment,
        'form': form,
        'readonly': False,
        'now': timezone.now(),
        'ai_grade': None,
        'content_html': content_html,   # <-- tärkeä lisä
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

    # --- AI-rubriikkiarviointi: luonti napista ---
    if request.method == 'POST' and 'run_ai_grade' in request.POST:
        try:
            ag = create_or_update_ai_grade(submission)
            messages.success(request, f"AI-arviointiehdotus luotu ({ag.total_points:.1f} p).")
        except Exception as e:
            messages.error(request, f"AI-arviointi epäonnistui: {e}")
        return redirect('grade_submission', submission_id=submission.id)

    # --- AI-rubriikkiarviointi: hyväksy ehdotus kenttiin ---
    if request.method == 'POST' and 'accept_ai_grade' in request.POST:
        ag = getattr(submission, 'ai_grade', None)
        if not ag:
            messages.error(request, "AI-arviointiehdotusta ei ole.")
            return redirect('grade_submission', submission_id=submission.id)

        # Kopioi kriteerikohtaiset pisteet ja palautteet submissionin kenttiin
        max_total = sum(int(c.get("max", 0)) for c in ag.details.get("criteria", []))
        submission.score = ag.total_points
        submission.max_score = max_total or None

        lines = []
        for c in ag.details.get("criteria", []):
            lines.append(f"- {c.get('name')}: {c.get('points')}/{c.get('max')} – {c.get('feedback')}")
        gen = ag.details.get("general_feedback") or ""
        if gen:
            lines.append("")
            lines.append(gen)
        submission.feedback = "\n".join(lines).strip()
        submission.save(update_fields=["score", "max_score", "feedback"])

        messages.success(request, "AI-ehdotus kopioitu arviointikenttiin. Voit vielä muokata ja tallentaa.")
        return redirect('grade_submission', submission_id=submission.id)

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

    # Viedään mahdolliset raportit/ehdotukset templaatille
    plagiarism_report = getattr(submission, "plagiarism_report", None)
    ai_grade = getattr(submission, "ai_grade", None)

    return render(request, 'assignments/grade.html', {
        'material': material,
        'assignment': assignment,
        'submission': submission,
        'form': form,
        'plagiarism_report': plagiarism_report,
        'ai_grade': ai_grade,
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

@login_required
def add_material_image_view(request, material_id):
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta.")
        return redirect("material_detail", material_id=m.id)

    form = AddImageForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upload  = form.cleaned_data["upload"]
        prompt  = (form.cleaned_data["gen_prompt"] or "").strip()
        caption = form.cleaned_data["caption"] or ""

        def append_image_to_content(image_url: str, cap: str):
            md_img = f"![{cap or 'Kuva'}]({image_url})"
            m.content = (m.content or "").rstrip()
            m.content += (("\n\n" if m.content else "") + md_img + "\n")
            m.save(update_fields=["content"])

        # 1) Tiedosto
        if upload:
            mi = MaterialImage.objects.create(
                material=m, image=upload, caption=caption, created_by=request.user
            )
            append_image_to_content(mi.image.url, caption)
            messages.success(request, "Kuva lisätty sisältöön.")
            return redirect("material_detail", material_id=m.id)

        # 2) Generointi (käyttää ai_service.py:n funktiota)
        if prompt:
            try:
                from .ai_service import generate_image_bytes  # AI-koodi pysyy ai_service.py:ssä
                data = generate_image_bytes(prompt, size="1024x1024")
                if not data:
                    messages.error(request, "API-avain puuttuu tai generointi ei palauttanut dataa.")
                else:
                    from django.core.files.base import ContentFile
                    mi = MaterialImage.objects.create(
                        material=m,
                        image=ContentFile(data, name="gen.png"),
                        caption=caption,
                        created_by=request.user,
                    )
                    append_image_to_content(mi.image.url, caption)
                    messages.success(request, "Generoitu kuva lisätty sisältöön.")
                    return redirect("material_detail", material_id=m.id)
            except Exception as e:
                messages.error(request, f"Kuvan generointi epäonnistui: {e}")
                return redirect("material_detail", material_id=m.id)

        messages.error(request, "Valitse tiedosto tai anna generointikehote.")
        return redirect("material_detail", material_id=m.id)

    return render(request, "materials/add_image.html", {"material": m, "form": form})


@login_required
def edit_material_view(request, material_id):
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta.")
        return redirect("material_detail", material_id=m.id)

    if request.method == "POST":
        form = MaterialForm(request.POST, instance=m)
        if form.is_valid():
            form.save()
            messages.success(request, "Materiaali päivitetty.")
            return redirect("material_detail", material_id=m.id)
    else:
        form = MaterialForm(instance=m)

    return render(request, "materials/edit.html", {"material": m, "form": form})

@login_required
def unassign_view(request, assignment_id):
    a = get_object_or_404(Assignment, pk=assignment_id)
    if request.user.role != "TEACHER" or a.assigned_by_id != request.user.id:
        messages.error(request, "Ei oikeutta.")
        return redirect("view_submissions", material_id=a.material_id)
    a.delete()
    messages.success(request, "Tehtävänanto poistettu tältä oppilaalta.")
    return redirect("view_submissions", material_id=a.material_id)

@login_required
def assign_material_view(request, material_id):
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta.")
        return redirect("material_detail", material_id=m.id)

    if request.method == "POST":
        form = AssignForm(request.POST, teacher=request.user)
        if form.is_valid():
            due_at = form.cleaned_data["due_at"]
            give_to_class = form.cleaned_data["give_to_class"]
            class_number = form.cleaned_data["class_number"]
            students = form.cleaned_data["students"]

            targets = []
            if give_to_class and class_number:
                from users.models import CustomUser
                targets = list(CustomUser.objects.filter(role="STUDENT", grade_class=class_number))
            else:
                targets = list(students)

            created = 0
            for st in targets:
                Assignment.objects.get_or_create(
                    material=m, student=st,
                    defaults={"assigned_by": request.user, "due_at": due_at}
                )
                created += 1
            messages.success(request, f"Annettu {created} oppilaalle.")
            return redirect("material_detail", material_id=m.id)
    else:
        form = AssignForm(teacher=request.user)

    return render(request, "assignments/assign.html", {"material": m, "form": form})


@login_required
def unassign_assignment(request, assignment_id):  # assignment_id on UUID, koska urls käyttää <uuid:...>
    # sallitaan vain opettajille
    if not hasattr(request.user, "role") or request.user.role != "TEACHER":
        return HttpResponseForbidden("Vain opettaja voi poistaa tehtävänannon.")

    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == "POST":
        title = assignment.material.title
        student_name = assignment.student.get_full_name() or assignment.student.username
        assignment.delete()
        messages.success(request, f"Tehtävänanto poistettu: '{title}' → {student_name}.")
        return redirect("dashboard")

    # GET: ei tehdä poistoa, vain takaisin
    return redirect("dashboard")

@require_POST
def generate_image_view(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads((request.body or b"").decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = request.POST

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return JsonResponse({"error": "Tyhjä prompt"}, status=400)

    size_str = "1024x1024"
    rel_dir = "ai_images"
    os.makedirs(os.path.join(settings.MEDIA_ROOT, rel_dir), exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, filename)
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)

    try:
        image_bytes = generate_image_bytes(prompt=prompt, size=size_str)
        if not image_bytes:
            return JsonResponse({"error": "Generointi palautti tyhjän tuloksen."}, status=502)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)

    with open(abs_path, "wb") as f:
        f.write(image_bytes)

    image_url = urljoin(settings.MEDIA_URL, rel_path.replace(os.sep, "/"))
    return JsonResponse({"image_url": image_url}, status=201)

def material_detail_view(request, material_id):
    material = get_object_or_404(Material, pk=material_id)
    rendered = mark_safe(md.markdown(material.content or "", extensions=["extra"]))
    return render(request, "materials/material_detail.html", {
        "material": material,
        "rendered_content": rendered,
    })

@login_required
@require_POST
def delete_material_image_view(request, image_id):
    img = get_object_or_404(MaterialImage.objects.select_related("material"), pk=image_id)

    # vain materiaalin tekijä/opettaja saa poistaa
    if request.user.role != "TEACHER" or img.material.author_id != request.user.id:
        return HttpResponseForbidden("Ei oikeutta poistaa kuvaa.")

    material_id = img.material_id
    img.delete()  # post_delete-signaali poistaa myös tiedoston levyltä
    messages.success(request, "Kuva poistettu.")
    return redirect("material_detail", material_id=material_id)

@require_POST
@login_required(login_url='kirjaudu')
def material_image_insert_view(request, material_id, image_id):
    """Lisää valitun galleria-kuvan markdown-tagina materiaalin contentiin."""
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta muokata tämän materiaalin sisältöä.")
        return redirect("material_detail", material_id=m.id)

    img = get_object_or_404(MaterialImage, pk=image_id, material=m)

    alt = (img.caption or "Kuva").strip()
    url = img.image.url          # esim. /media/materials/2025/09/kuva.png
    md  = f"\n\n![{alt}]({url})\n"

    m.content = (m.content or "")
    if m.content and not m.content.endswith("\n"):
        m.content += "\n"
    m.content += md
    m.save(update_fields=["content"])

    messages.success(request, "Kuva lisättiin sisältöön.")
    return redirect("material_detail", material_id=m.id)

@require_POST
def generate_image_view(request):
    # 1) Payload
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads((request.body or b"").decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = request.POST

    prompt = (payload.get("prompt") or "").strip()
    size_key = (payload.get("size") or "square").strip().lower()
    if not prompt:
        return JsonResponse({"error": "Tyhjä prompt"}, status=400)

    # 2) Haluttu LOPPUTULOS (näytettävä kuva)
    out_map = {
        "square":   (1024, 1024),
        "landscape": (1344, 768),
        "portrait":  (768, 1344),
    }
    out_w, out_h = out_map.get(size_key, out_map["square"])
    out_size_str = f"{out_w}x{out_h}"

    # 3) DALL·E 2: generoidaan aina 1024×1024 ja muokataan sitten
    gen_w, gen_h = 1024, 1024
    rel_dir = "ai_images"
    os.makedirs(os.path.join(settings.MEDIA_ROOT, rel_dir), exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, filename)
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)

    used_placeholder = False
    last_error = None
    image_bytes = None

    try:
        # bytes DALL·E 2:lta (tai demo-bitti ai_service.py:stä)
        from .ai_service import generate_image_bytes
        data = generate_image_bytes(prompt, size=f"{gen_w}x{gen_h}")  # DALL·E 2: vain neliö
        if data:
            # 4) Jälkikäsittely: rajaa TAI letterboxaa haluttuun kokoon
            img = Image.open(io.BytesIO(data)).convert("RGB")

            # a) “Smart crop”: täytetään koko, mahdollinen reunoista leikkaus
            fitted = ImageOps.fit(img, (out_w, out_h), method=Image.LANCZOS, centering=(0.5, 0.5))

            # Jos haluat letterboxin croppauksen sijaan, korvaa yllä oleva:
            # contained = ImageOps.contain(img, (out_w, out_h), method=Image.LANCZOS)
            # canvas = Image.new("RGB", (out_w, out_h), (20,24,28))
            # x = (out_w - contained.width)//2
            # y = (out_h - contained.height)//2
            # canvas.paste(contained, (x,y))
            # fitted = canvas

            buf = io.BytesIO()
            fitted.save(buf, "PNG")
            image_bytes = buf.getvalue()
        else:
            used_placeholder = True
    except Exception as e:
        used_placeholder = True
        last_error = str(e)

    if used_placeholder:
        img = Image.new("RGB", (out_w, out_h), (20, 24, 28))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", size=28)
        except Exception:
            font = ImageFont.load_default()
        draw.multiline_text(
            (40, 40),
            f"AI-kuva ({out_size_str})\n\n{prompt}",
            font=font, fill=(220, 230, 240), spacing=6
        )
        buf = io.BytesIO(); img.save(buf, "PNG"); image_bytes = buf.getvalue()

    # 5) Tallenna ja palauta
    with open(abs_path, "wb") as f:
        f.write(image_bytes)

    image_url = urljoin(settings.MEDIA_URL, rel_path.replace(os.sep, "/"))
    return JsonResponse(
        {"image_url": image_url, "placeholder": used_placeholder, "error": last_error},
        status=201 if not used_placeholder else 207
    )

_MD_IMG = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def render_material_content_to_html(text: str) -> str:
    """
    Kevyt renderöinti: muutetaan Markdown-kuvat <img>-tageiksi ja säilytetään rivinvaihdot.
    Jos haluat täyden markdown-renderöinnin, korvaa tämä md.markdown()-kutsulla.
    """
    if not text:
        return ""
    html = _MD_IMG.sub(
        r'<figure class="my-3"><img src="\2" alt="\1" class="img-fluid rounded border">'
        r'<figcaption class="small text-muted">\1</figcaption></figure>',
        text,
    )
    html = html.replace("\n", "<br>")
    return mark_safe(html)