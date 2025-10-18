from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
import json

from ..models import Assignment, Submission
from ..forms import SubmissionForm
from .shared import render_material_content_to_html # Jaettu apufunktio

# --- Oppilaan Dashboard ---
@login_required(login_url='kirjaudu')
def student_dashboard_view(request):
    user = request.user
    selected_subject = request.GET.get('subject', '')
    qs = Assignment.objects.select_related('material', 'assigned_by').filter(student=user)

    if selected_subject:
        qs = qs.filter(material__subject=selected_subject)

    qs_for_display = qs.exclude(status='GRADED', material__material_type='peli')

    counts = {
        "assigned": qs_for_display.filter(status=Assignment.Status.ASSIGNED).count(),
        "in_progress": qs_for_display.filter(status=Assignment.Status.IN_PROGRESS).count(),
        "graded": qs_for_display.filter(status=Assignment.Status.GRADED).count(),
    }
    due_soon = qs_for_display.exclude(due_at__isnull=True).filter(due_at__gte=timezone.now()).order_by('due_at')[:3]
    subjects = Assignment.objects.filter(student=user).exclude(material__subject__isnull=True).exclude(material__subject='').values_list('material__subject', flat=True).distinct().order_by('material__subject')

    return render(request, 'dashboard/student.html', {
        "counts": counts, "due_soon": due_soon, "subjects": subjects, "selected_subject": selected_subject
    })

@login_required(login_url='kirjaudu')
def student_assignments_view(request):
    """
    Näyttää oppilaalle kaikki hänelle jaetut tehtävät (pl. suoritetut pelit).
    Mahdollisuus suodattaa tehtäviä statuksen ja oppiaineen mukaan.

    Args:
        request: HTTP-pyyntö.

    Returns:
        HttpResponse: Renderöity oppilaan tehtävälistaussivu.
    """
    user = request.user
    if user.role != 'STUDENT':
        return redirect('dashboard')

    selected_status = request.GET.get('status', '')
    selected_subject = request.GET.get('subject', '')

    # MUUTETTU: Suodata pois GRADED-statuksen tehtävät (suoritetut pelit)
    qs = Assignment.objects.select_related('material', 'assigned_by').filter(
        student=user
    ).exclude(
        status='GRADED',  # Piilota suoritetut pelit
        material__material_type='peli'  # Vain pelit piilotetaan
    )

    # Suodatus
    subjects = qs.exclude(material__subject__isnull=True).exclude(material__subject='').values_list('material__subject', flat=True).distinct().order_by('material__subject')

    if selected_status:
        qs = qs.filter(status=selected_status)
    
    if selected_subject:
        qs = qs.filter(material__subject=selected_subject)

    ctx = {
        "assigned": qs.filter(status="ASSIGNED"),
        "in_progress": qs.filter(status="IN_PROGRESS"),
        "submitted": qs.filter(status__in=["SUBMITTED"]),  # GRADED ei enää mukana
        "subjects": subjects,
        "selected_subject": selected_subject,
        "selected_status": selected_status,
        "now": timezone.now(),
    }
    return render(request, 'student/assignments.html', ctx)

@login_required(login_url='kirjaudu')
def student_grades_view(request):
    """
    Oppilaan palautukset ja arvioinnit:
    - Näyttää SUBMITTED ja GRADED -tilassa olevat tehtävät.
    - Haku materiaalin nimellä tai opettajan nimellä.
    - Sivutus.

    Args:
        request: HTTP-pyyntö.

    Returns:
        HttpResponse: Renderöity oppilaan arvosanasivu.
    """
    if request.user.role != 'STUDENT':
        return redirect('dashboard')

    q = (request.GET.get('q') or '').strip()

    qs = (Assignment.objects
          .select_related('material', 'assigned_by')
          .filter(student=request.user, status__in=['SUBMITTED', 'GRADED'])
          .exclude(material__material_type='peli')  # ← TÄRKEÄ: Suodata pelit pois
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

# Oppilaan pelinäkymä 
@login_required(login_url='kirjaudu')
def student_games_view(request):
    """
    Oppilaan pelisivu - näyttää kaikki pelit (myös suoritetut).

    Toiminnot:
    - Hakee kaikki oppilaan pelit (material_type='peli').
    - Aihesuodatus (subject).
    - Jakaa pelit kolmeen kategoriaan: uudet, keskeneräiset, suoritetut.

    Args:
        request: HTTP-pyyntö.

    Returns:
        HttpResponse: Renderöity 'student/games.html' -template.
    """
    if request.user.role != 'STUDENT':
        return redirect('dashboard')

    selected_subject = request.GET.get('subject', '')

    # Hae kaikki pelit (mukaan lukien suoritetut)
    qs = Assignment.objects.select_related('material', 'assigned_by').filter(
        student=request.user,
        material__material_type='peli'
    ).order_by('-created_at')

    # Aihesuodatus
    subjects = qs.exclude(
        material__subject__isnull=True
    ).exclude(
        material__subject=''
    ).values_list('material__subject', flat=True).distinct().order_by('material__subject')

    if selected_subject:
        qs = qs.filter(material__subject=selected_subject)

    # Jaa pelit kategorioihin
    ctx = {
        "assigned": qs.filter(status="ASSIGNED"),
        "completed": qs.filter(status__in=["SUBMITTED", "GRADED"]),
        "subjects": subjects,
        "selected_subject": selected_subject,
        "now": timezone.now(),
    }
    return render(request, 'student/games.html', ctx)

@login_required(login_url='kirjaudu')
def assignment_detail_view(request, assignment_id):
    """
    Oppilaan näkymä yksittäiselle tehtävälle. Mahdollistaa tehtävän
    sisällön katselun, luonnoksen tallentamisen ja lopullisen
    vastauksen lähettämisen. Ohjaa pelit erilliselle pelinäkymälle.

    Args:
        request: HTTP-pyyntö.
        assignment_id (uuid.UUID): Tehtävän ID.

    Returns:
        HttpResponse: Renderöity tehtävän yksityiskohtien sivu
                      tai ohjaus pelinäkymään.
    """
    assignment = get_object_or_404(
        Assignment.objects.select_related('material', 'student', 'assigned_by'),
        id=assignment_id
    )

    # Oikeustarkistus
    if assignment.student_id != request.user.id:
        messages.error(request, "Sinulla ei ole oikeuksia nähdä tätä tehtävää.")
        return redirect('dashboard')

    # --- TÄMÄ ON TÄRKEIN UUSI LISÄYS ---
    # Jos materiaali on peli, ohjataan suoraan pelinäkymään
    if assignment.material.material_type == 'peli':
        return redirect('play_game', assignment_id=assignment.id)
    # --- LISÄYS PÄÄTTYY ---

    # Jos materiaali EI ole peli, jatketaan normaalisti vanhalla logiikalla:
    content_html = render_material_content_to_html(assignment.material.content)

    if assignment.status in (Assignment.Status.SUBMITTED, Assignment.Status.GRADED):
        # ... (TÄHÄN TULEE KOKO LOPPUOSA VANHASTA FUNKTIOSTASI, SITÄ EI TARVITSE MUUTTAA) ...
        # ... (alkaa 'form = SubmissionForm()' ...)
        form = SubmissionForm()
        last_sub = assignment.submissions.last()
        ai_grade = getattr(last_sub, 'ai_grade', None) if last_sub else None
        return render(request, 'assignments/detail.html', {
            'assignment': assignment,
            'form': form,
            'readonly': True,
            'now': timezone.now(),
            'ai_grade': ai_grade,
            'content_html': content_html,
        })

    if request.method == 'POST':
        # ... (TÄHÄN TULEE KOKO LOPPUOSA VANHASTA FUNKTIOSTASI, SITÄ EI TARVITSE MUUTTAA) ...
        # ... (alkaa 'form = SubmissionForm(request.POST)' ...)
        form = SubmissionForm(request.POST)
        if 'save_draft' in request.POST:
            assignment.draft_response = request.POST.get('response', '').strip()
            if assignment.draft_response and assignment.status == Assignment.Status.ASSIGNED:
                assignment.status = Assignment.Status.IN_PROGRESS
            assignment.save(update_fields=['draft_response', 'status'])
            messages.info(request, "Luonnos tallennettu onnistuneesti!")
            return redirect('assignment_detail', assignment_id=assignment.id)
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
        form = SubmissionForm(initial={'response': assignment.draft_response})
    
    return render(request, 'assignments/detail.html', {
        'assignment': assignment,
        'form': form,
        'readonly': False,
        'now': timezone.now(),
        'ai_grade': None,
        'content_html': content_html,
    })

@login_required(login_url='kirjaudu')
def play_game_view(request, assignment_id):
    """
    Käsittelee pelitehtävän pelaamisen ja vastausten lähettämisen.

    Vaatii käyttäjän olevan kirjautuneena sisään.
    Varmistaa, että tehtävä kuuluu kirjautuneelle käyttäjälle ja että materiaali on tyypiltään 'peli'.

    Args:
        request: HttpRequest-objekti.
        assignment_id: Pelattavan Assignment-objektin ID.

    Returns:
        HttpResponse: Renderöity HTML-sivu pelin pelaamiseksi tai ohjaus toiselle sivulle.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Varmistetaan, että vain oikea oppilas pääsee pelaamaan
    if assignment.student != request.user:
        messages.error(request, "Tämä tehtävä ei ole sinulle.")
        return redirect('dashboard')

    # Varmistetaan, että materiaali on peli
    if assignment.material.material_type != 'peli':
        messages.error(request, "Tämä materiaali ei ole peli.")
        return redirect('assignment_detail', assignment_id=assignment.id)

    context = {
        'assignment': assignment,
        # Välitetään pelin data (kysymykset yms.) suoraan templatelle JSON-muodossa
        'game_data_json': json.dumps(assignment.material.structured_content)
    }
    return render(request, 'assignments/play_game.html', context)

'''    # Muokkaustila -> Kommentoitu ulos, koska koodia ei koskaan suoriteta
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
    }) '''