# materials/views/teacher.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseNotAllowed, JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.utils import timezone
import csv
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from users.models import CustomUser
from ..models import Material, Assignment, Submission, MaterialImage
from ..forms import MaterialForm, AssignForm, GradingForm, AddImageForm
from ..ai_service import ask_llm, ask_llm_with_ops, generate_image_bytes
from ..ai_rubric import create_or_update_ai_grade
from ..plagiarism import build_or_update_report
from .shared import format_game_content_for_display, render_material_content_to_html
from TaskuOpe.ops_chunks import get_facets
from urllib.parse import urljoin
from django.core.files.storage import default_storage


# --- Opettajan Dashboard ---
@login_required(login_url='kirjaudu')
def teacher_dashboard_view(request):

    """
    Näyttää opettajan dashboard-sivun, jossa on lista
    hänen materiaaleistaan ja tehtävänannoistaan.
    """
    user = request.user
    materials_qs = Material.objects.filter(author=user)
    subjects = materials_qs.exclude(subject__isnull=True).exclude(subject='').values_list('subject', flat=True).distinct().order_by('subject')

    selected_subject = request.GET.get('subject', '')
    
    materials_to_display = Material.objects.none()
    if selected_subject:
        materials_to_display = materials_qs.filter(subject=selected_subject)

    assignments = (
        Assignment.objects
        .filter(assigned_by=user)
        .select_related('material', 'student')
        .order_by('-created_at')
    )
    context = {
        'materials': materials_to_display,
        'assignments': assignments,
        'subjects': subjects,
        'selected_subject': selected_subject
    }
    return render(request, 'dashboard/teacher.html', context)


@login_required(login_url='kirjaudu')
def create_material_view(request):

    """
    Manuaalinen materiaalin luonti, tekoälyavustin ja pelin generointi.
    Opettaja voi luoda uuden materiaalin käsin, käyttää tekoälyä sisällön
    generointiin tai luoda tekoälyn avulla pelin.

    Args:
        request: HTTP-pyyntö.

    Returns:
        HttpResponse: Renderöity materiaalin luontisivu.
    """
    if request.user.role != 'TEACHER':
        return redirect('dashboard')

    ops_facets = get_facets()
    ai_reply = None
    ai_prompt_val = ""
    ops_vals = {
        'use_ops': request.POST.get('use_ops') == 'on',
        'ops_subject': request.POST.get('ops_subject', ''),
        'ops_grade': request.POST.get('ops_grade', ''),
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        form = MaterialForm(request.POST)

        if action == 'ai':
            ai_prompt_val = (request.POST.get('ai_prompt') or '').strip()
            if ai_prompt_val:
                if ops_vals['use_ops'] and ops_vals['ops_subject'] and ops_vals['ops_grade']:
                    result = ask_llm_with_ops(
                        question=ai_prompt_val, subjects=[ops_vals['ops_subject']],
                        grades=[ops_vals['ops_grade']], user_id=request.user.id
                    )
                    ai_reply = result.get('answer', '[Virhe haettaessa OPS-dataa]')
                else:
                    ai_reply = ask_llm(ai_prompt_val, user_id=request.user.id)
            
            return render(request, 'materials/create.html', {
                'form': form, 'ai_prompt': ai_prompt_val, 'ai_reply': ai_reply,
                'ops_vals': ops_vals, 'ops_facets': ops_facets
            })

        if action == 'save' or action is None:
            if form.is_valid():
                material = form.save(commit=False)
                material.author = request.user

                if material.material_type == 'peli':
                    json_data_str = request.POST.get('structured_content_json')
                    if json_data_str:
                        try:
                            # Parsitaan JSON
                            game_json = json.loads(json_data_str)
            
                            # Tallennetaan structured_content-kenttään (JSONField)
                            material.structured_content = game_json
            
                            # Muotoillaan content-kenttään (TextField) opettajalle näkyvä versio
                            material.content = format_game_content_for_display(game_json)
                        except Exception as e:
                            # Jos JSON-parsinta epäonnistuu, tallenna raaka data
                            material.content = f"Virhe pelin datan käsittelyssä:\n\n{json_data_str}"
                    else:
                        messages.error(request, "Valitsit materiaaliksi 'Peli', mutta et generoinut pelisisältöä. Käytä 'Generoi peli' -toimintoa ennen tallennusta.")
                        return render(request, 'materials/create.html', {
                            'form': form, 'ops_vals': ops_vals, 'ops_facets': ops_facets
                        })
                
                material.save()
                messages.success(request, f"Materiaali '{material.title}' tallennettu onnistuneesti.")
                return redirect('dashboard')
            else:
                messages.error(request, "Lomakkeessa oli virheitä. Tarkista tiedot.")
        
    else: # GET-pyyntö
        form = MaterialForm()

    return render(request, 'materials/create.html', {
        'form': form, 'ai_prompt': '', 'ai_reply': None,
        'ops_vals': {'use_ops': False, 'ops_subject': '', 'ops_grade': ''},
        'ops_facets': ops_facets
    })

@login_required(login_url='kirjaudu')
def material_list_view(request):
    """
    Listaa kaikki opettajan luomat materiaalit, mahdollistaa
    suodatuksen oppiaineen mukaan.

    Args:
        request: HTTP-pyyntö.

    Returns:
        HttpResponse: Renderöity materiaalien listaussivu.
    """
    if request.user.role != 'TEACHER':
        messages.error(request, "Vain opettajat voivat nähdä tämän sivun.")
        return redirect('dashboard')

    selected_subject = request.GET.get('subject', '')
    all_materials = Material.objects.filter(author=request.user).order_by('created_at')
    
    # UUSI: Erottele pelit ja normaalit materiaalit
    normal_materials = all_materials.exclude(material_type='peli')
    game_materials = all_materials.filter(material_type='peli')

    # Aihesuodatus
    subjects = all_materials.exclude(subject__isnull=True).exclude(subject='').values_list('subject', flat=True).distinct().order_by('subject')

    if selected_subject:
        normal_materials = normal_materials.filter(subject=selected_subject)
        game_materials = game_materials.filter(subject=selected_subject)

    context = {
        'materials': normal_materials,  # Normaalit materiaalit
        'games': list(game_materials[:50]),  # Pelit erikseen
        'subjects': subjects,
        'selected_subject': selected_subject,
    }
    return render(request, 'materials/list.html', context)

@login_required
def edit_material_view(request, material_id):
    """
    Käsittelee opettajan luoman materiaalin muokkaamisen.

    Varmistaa, että käyttäjällä on opettajan rooli ja että hän on
    materiaalin tekijä. Näyttää lomakkeen materiaalin tietojen muokkaamiseen
    ja tallentaa muutokset tietokantaan.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Muokattavan materiaalin yksilöivä ID.

    Returns:
        HttpResponse: Renderöity HTML-sivu muokkauslomakkeella tai
                      uudelleenohjaus onnistuneen tallennuksen jälkeen
                      tai jos käyttäjällä ei ole oikeuksia.
    """
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

# --- Deletion ---
@login_required(login_url='kirjaudu')
def delete_material_view(request, material_id):
    """
    Poistaa opettajan luoman materiaalin ja ohjaa käyttäjän takaisin
    sivulle, jolta poisto tehtiin.
    """
    material = get_object_or_404(Material, id=material_id, author=request.user)
    
    if request.method == "POST":
        title = material.title
        material.delete()
        messages.success(request, f"Materiaali '{title}' poistettu.")

        # --- TÄSSÄ ON UUSI, ÄLYKÄS OHJAUS ---
        # Haetaan URL, jolta pyyntö tehtiin.
        referer_url = request.META.get('HTTP_REFERER')

        # Jos lähtösivu on olemassa, ohjataan sinne takaisin.
        # Muussa tapauksessa ohjataan turvallisesti etusivulle.
        if referer_url:
            return redirect(referer_url)
        else:
            return redirect('dashboard')
    
    # Jos pyyntö ei ole POST, ei sallita (tämä on hyvä turvatoimi)
    return HttpResponseNotAllowed(["POST"])

@login_required(login_url='kirjaudu')
def delete_assignment_view(request, assignment_id):
    """
    Poistaa opettajan luoman tehtävänannon.

    Varmistaa, että tehtävänanto kuuluu pyynnön tehneelle opettajalle.
    Hyväksyy vain POST-pyynnöt.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id, assigned_by=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    assignment.delete()
    messages.success(request, "Tehtävänanto poistettu.")
    return redirect('dashboard')

@login_required
def assign_material_view(request, material_id):
    """
    Käsittelee materiaalin jakamisen opiskelijoille tai luokille.

    Varmistaa, että käyttäjä on opettaja ja materiaalin tekijä.
    Käyttäjä voi valita yksittäisiä opiskelijoita tai kokonaisen luokan.
    Luo uusia Assignment-objekteja tai päivittää olemassa olevia.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Materiaalin yksilöivä ID, joka jaetaan.

    Returns:
        HttpResponse: Renderöity HTML-sivu jakamislomakkeella tai
                      uudelleenohjaus onnistuneen jakamisen jälkeen
                      tai jos käyttäjällä ei ole oikeuksia.
    """
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

    """
    Poistaa yksittäisen tehtävänannon opiskelijalta.

    Varmistaa, että pyynnön tekijä on opettaja ja että hänellä on oikeus
    poistaa kyseinen tehtävänanto (oletus: opettajan itse antama).
    Hyväksyy vain POST-pyynnöt poistotoiminnolle.

    Args:
        request: HttpRequest-objekti.
        assignment_id (uuid.UUID): Poistettavan tehtävänannon UUID.

    Returns:
        HttpResponse: Uudelleenohjaus 'dashboard'-sivulle onnistuneen
                      poiston jälkeen, tai jos käyttäjällä ei ole oikeuksia
                      tai HTTP-metodi ei ole POST. Palauttaa HttpResponseForbidden,
                      jos käyttäjällä ei ole opettajan roolia.
    """
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

# --- Submissions & Grading ---
@login_required(login_url='kirjaudu')
def view_submissions(request, material_id):
    """
    Opettajakäyttäjä: Näyttää kaikki opiskelijoiden palautukset tietylle materiaalille.

    Tarkistaa käyttäjän roolin ja materiaalikohtaiset oikeudet.
    Hakee kaikki lähetetyt tai arvioidut tehtävät kyseiselle materiaalille.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Materiaalin yksilöivä ID.

    Returns:
        HttpResponse: Renderöity HTML-sivu, joka näyttää tehtäväpalautukset,
                      tai uudelleenohjaus 'dashboard'-sivulle, jos oikeudet puuttuvat.
    """
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

# Arvosanan laskenta pistemäärästä
def _calculate_grade_from_score(score, max_score):
    """
    Muuntaa annetun pistemäärän arvosanaksi (4-10) prosenttiosuuden perusteella.

    HUOM: Arvosanarajojen prosenttiosuuksia voi muokata tarpeen mukaan.

    Args:
        score (int | float): Opiskelijan saama pistemäärä.
        max_score (int | float): Tehtävän maksimipistemäärä.

    Returns:
        int | None: Lasketun arvosanan (kokonaisluku 4-10) tai None,
                    jos syöte on virheellinen tai maksimipisteet ovat nolla.
    """
    # Ensure the values are numbers and avoid division by zero
    try:
        score_num = float(score)
        max_score_num = float(max_score)
        if max_score_num == 0:
            return None
    except (TypeError, ValueError):
        return None  # Return None if score is not defined

    percentage = (score_num / max_score_num) * 100

    if percentage < 40:
        return 4
    elif percentage < 50:
        return 5
    elif percentage < 60:
        return 6
    elif percentage < 70:
        return 7
    elif percentage < 80:
        return 8
    elif percentage < 90:
        return 9
    else:
        return 10

@login_required(login_url='kirjaudu')
@transaction.atomic
def grade_submission_view(request, submission_id):
    """
    Käsittelee tehtävän palautuksen arvioinnin ja plagioinnin tarkistuksen.

    Mahdollistaa opettajalle arvosanan antamisen ja tallentamisen,
    sekä alkuperäisyysraportin luomisen tai päivittämisen pyynnöstä.

    Args:
        request: HttpRequest-objekti.
        submission_id (int): Arvioitavan palautuksen (Submission) ID.

    Returns:
        HttpResponse: Renderöity HTML-sivu arviointilomakkeineen ja raportteineen,
                      tai uudelleenohjaus onnistuneen tallennuksen jälkeen.
    """
    submission = get_object_or_404(
        Submission.objects.select_related('assignment__student', 'assignment__material'),
        id=submission_id
    )
    assignment = submission.assignment
    material = assignment.material

    # Authorization check
    if request.user.role != "TEACHER" or material.author_id != request.user.id:
        messages.error(request, "Sinulla ei ole oikeuksia arvioida tätä palautusta.")
        return redirect('dashboard')

    # --- AI rubric grading: generate from button press ---
    if request.method == 'POST' and 'run_ai_grade' in request.POST:
        try:
            ag = create_or_update_ai_grade(submission)
            messages.success(request, f"AI-arvosanaehdotus luotu ({ag.total_points:.1f} pistettä).")
        except Exception as e:
            messages.error(request, f"AI-arvosanaehdotuksen luonti epäonnistui: {e}")
        return redirect('grade_submission', submission_id=submission.id)

    # --- AI rubric grading: accept suggestion into fields ---
    if request.method == 'POST' and 'accept_ai_grade' in request.POST:
        ag = getattr(submission, 'ai_grade', None)
        if not ag:
            messages.error(request, "AI-arvosanaehdotus ei ole olemassa.")
            return redirect('grade_submission', submission_id=submission.id)

        # Copy criterion-specific scores and feedback to submission fields
        max_total = sum(int(c.get("max", 0)) for c in ag.details.get("criteria", []))
        submission.score = ag.total_points
        submission.max_score = max_total or None

        # Format the feedback text
        lines = []
        for c in ag.details.get("criteria", []):
            lines.append(f"- {c.get('name')}: {c.get('points')}/{c.get('max')} – {c.get('feedback')}")
        gen_feedback = ag.details.get("general_feedback") or ""
        if gen_feedback:
            lines.append("")
            lines.append(gen_feedback)
        submission.feedback = "\n".join(lines).strip()

        # Calculate and set the grade using the new helper function
        calculated_grade = _calculate_grade_from_score(submission.score, submission.max_score)
        if calculated_grade is not None:
            submission.grade = calculated_grade
        # --- END OF ADDED PART ---

        # --- MODIFIED LINE: Added 'grade' to the list of fields to save ---
        submission.save(update_fields=["score", "max_score", "feedback", "grade"])

        messages.success(request, "AI-arvosanaehdotus kopioitu arviointikenttiin. Voit nyt muokata ja tallentaa.")
        return redirect('grade_submission', submission_id=submission.id)

    # --- Plagiarism check from button press ---
    if request.method == 'POST' and 'run_plagiarism' in request.POST:
        try:
            report = build_or_update_report(submission)
            if report.suspected_source:
                messages.success(
                    request,
                    f"Alkuperäisyysselvityksen raportti päivitetty. Samankaltaisuus: {report.score:.2f}"
                )
            else:
                messages.info(
                    request,
                    "Raportti päivitetty. Merkittävää samankaltaisuutta ei löytynyt."
                )
        except Exception as e:
            messages.error(request, f"Raportin luonti epäonnistui: {e}")
        return redirect('grade_submission', submission_id=submission.id)

    # --- Final form submission (saving the manual grade) ---
    if request.method == 'POST':
        form = GradingForm(request.POST, instance=submission)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.graded_at = timezone.now()
            sub.save()

            assignment.status = Assignment.Status.GRADED
            assignment.save(update_fields=['status'])

            messages.success(request, "Arvosana tallennettu onnistuneesti.")
            return redirect('view_submissions', material_id=material.id)
    else:
        form = GradingForm(instance=submission)

    # Pass potential reports and suggestions to the template
    plagiarism_report = getattr(submission, "plagiarism_report", None)
    ai_grade = getattr(submission, "ai_grade", None)

    # pelin HTML-esikatselu) renderöitäväksi HTML-koodiksi.
    rendered_material_content = render_material_content_to_html(material.content)
    # =================================================================

    return render(request, 'assignments/grade.html', {
        'material': material,
        'assignment': assignment,
        'submission': submission,
        'form': form,
        'plagiarism_report': plagiarism_report,
        'ai_grade': ai_grade,
        'rendered_material_content': rendered_material_content,
    })

@login_required(login_url='kirjaudu')
def view_all_submissions_view(request):
    """
    Opettajakäyttäjä: Näyttää listan kaikista opettajan luomien materiaalien
    perusteella luoduista tehtäväpalautuksista.

    Mahdollistaa palautusten suodattamisen tilan (lähetetty/arvioitu) ja
    hakusanan perusteella. Erottaa "normaalit" tehtävät ja "pelitehtävät"
    eri listoihin.

    Args:
        request: HttpRequest-objekti.

    Returns:
        HttpResponse: Renderöity HTML-sivu, joka näyttää tehtäväpalautukset,
                      tai uudelleenohjaus 'dashboard'-sivulle, jos käyttäjällä
                      ei ole opettajan roolia.
    """
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

    # UUSI: Erottele pelit ja normaalit tehtävät
    normal_assignments = base.exclude(material__material_type='peli')
    game_assignments = base.filter(material__material_type='peli')

    # Sivutus normaaleille tehtäville
    page = Paginator(normal_assignments, 20).get_page(request.GET.get("page"))
    
    # Pelit ilman sivutusta (näytetään kaikki collapse-laatikossa)
    games_list = list(game_assignments[:50])  # Rajoita max 50 peliä

    return render(request, 'assignments/submissions_list.html', {
        'assignments': page,  # Normaalit tehtävät (paginated)
        'games': games_list,  # Pelit (ei sivutusta)
        'q': q,
        'status': st or "",
    })

@login_required(login_url='kirjaudu')
def export_submissions_csv_view(request):
    """
    Opettajakäyttäjä: Luo ja palauttaa CSV-tiedoston, joka sisältää
    opettajan luomien tehtävien palautustiedot.

    Mahdollistaa palautusten suodattamisen tilan ja hakusanan perusteella.
    CSV-tiedosto sisältää tietoja opiskelijasta, materiaalista, tilasta,
    pisteistä, arvosanasta ja palautteesta.

    Args:
        request: HttpRequest-objekti.

    Returns:
        HttpResponse: CSV-tiedosto HTTP-vastauksena tai uudelleenohjaus
                      'dashboard'-sivulle, jos käyttäjällä ei ole
                      opettajan roolia.
    """
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
def teacher_student_list_view(request):

    """
    Käsittelee oppilastietojen näyttämistä ja päivittämistä opettajille.

    Varmistaa, että vain 'TEACHER'-roolissa olevat käyttäjät voivat
    käyttää tätä näkymää. Mahdollistaa opettajille opiskelijoiden
    luokkatiedon (grade_class) päivittämisen.
    """

    if request.user.role != 'TEACHER':
        messages.error(request, "Vain opettajat voivat hallita opiskelijoita.")
        return redirect('dashboard')

    if request.method == 'POST' and request.POST.get('action') == 'update_grades':
        for key, value in request.POST.items():
            if key.startswith('student-'):
                student_id = int(key.split('-')[1])
                try:
                    student = CustomUser.objects.get(id=student_id, role='STUDENT')
                    student.grade_class = int(value) if value else None
                    student.save(update_fields=['grade_class'])
                except (CustomUser.DoesNotExist, ValueError):
                    continue
        messages.success(request, "Oppilaiden luokkatiedot päivitetty.")
        return redirect('teacher_student_list')

    students = CustomUser.objects.filter(role='STUDENT').order_by('last_name', 'first_name')
    grade_choices = CustomUser._meta.get_field('grade_class').choices

    # HAKU-TOIMINTO
    students = CustomUser.objects.filter(role='STUDENT').order_by('last_name', 'first_name')

    q = (request.GET.get('q') or '').strip()
    if q:
        # Tee annotaatiot "etunimi sukunimi" ja "sukunimi etunimi"
        students = students.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name'),
            rev_full_name=Concat('last_name', Value(' '), 'first_name'),
        ).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(username__icontains=q)   |   # nimimerkki
            Q(full_name__icontains=q)  |   # "Etunimi Sukunimi"
            Q(rev_full_name__icontains=q)  # "Sukunimi Etunimi"
        )

    # Luokkasuodatin (?grade=2 luokka tms.)
    selected_grade = request.GET.get('grade', '').strip()
    if selected_grade:
        students = students.filter(grade_class=selected_grade)

    grade_choices = CustomUser._meta.get_field('grade_class').choices

    context = {
        'students': students,
        'grade_choices': grade_choices,
        'q': q,   # <-- välitetään templatelle
        'selected_grade': selected_grade,
    }

    return render(request, 'materials/teacher_student_list.html', context)

@login_required
def add_material_image_view(request, material_id):
    """
    Käsittelee kuvan lisäämisen materiaaliin. Toimii sekä tiedostolatauksella
    että AI-generoinnilla ja tallentaa tiedostot pilveen.
    """
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta.")
        return redirect("material_detail", material_id=m.id)

    if request.method == "POST":
        form = AddImageForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data.get("upload")
            prompt = (form.cleaned_data.get("gen_prompt") or "").strip()
            caption = form.cleaned_data.get("caption") or ""
            size_fragment = form.cleaned_data.get("size", "size-md")
            align_fragment = form.cleaned_data.get("alignment", "align-center")
            
            image_to_save = None
            
            if upload:
                image_to_save = upload
            elif prompt:
                try:
                    image_data = generate_image_bytes(prompt, size="1024x1024")
                    if image_data:
                        image_to_save = ContentFile(image_data, name="gen.png")
                    else:
                        messages.error(request, "Kuvan generointi ei palauttanut dataa.")
                except Exception as e:
                    messages.error(request, f"Kuvan generointi epäonnistui: {e}")
            
            if image_to_save:
                # Luo MaterialImage-objekti ilman tallennusta, jotta voimme asettaa polun
                mi = MaterialImage(material=m, caption=caption, created_by=request.user)
                # Tallenna tiedosto oletustallennustilaan (Spaces)
                mi.image.save(image_to_save.name, image_to_save, save=True)
                
                # Muodosta Markdown-linkki ja lisää se sisältöön
                final_url = f"{mi.image.url}#{size_fragment}-{align_fragment}"
                md_img = f"\n\n![{caption or 'Kuva'}]({final_url})\n"
                m.content = (m.content or "") + md_img
                m.save(update_fields=["content"])
                
                messages.success(request, "Kuva lisätty onnistuneesti sisältöön.")
                return redirect("material_detail", material_id=m.id)

    # Jos tultiin tänne asti, joko oli GET-pyyntö tai tapahtui virhe
    form = AddImageForm()
    return render(request, "materials/add_image.html", {"material": m, "form": form})
@login_required
@require_POST
def delete_material_image_view(request, image_id):
    """
    Poistaa materiaaliin liitetyn kuvan.
    """
    img = get_object_or_404(MaterialImage.objects.select_related("material"), pk=image_id)

    if request.user.role != "TEACHER" or img.material.author_id != request.user.id:
        return HttpResponseForbidden("Ei oikeutta poistaa kuvaa.")

    material_id = img.material_id
    img.delete()
    messages.success(request, "Kuva poistettu.")
    return redirect("material_detail", material_id=material_id)

@require_POST
@login_required(login_url='kirjaudu')
def material_image_insert_view(request, material_id, image_id):
    """
    Lisää valitun galleriakuvan Markdown-tagina materiaalin sisältökenttään.
    """
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta muokata tämän materiaalin sisältöä.")
        return redirect("material_detail", material_id=m.id)

    img = get_object_or_404(MaterialImage, pk=image_id, material=m)
    
    size_fragment = request.POST.get(f'size_{image_id}', 'size-md')
    align_fragment = request.POST.get(f'align_{image_id}', 'align-center')

    alt = (img.caption or "Kuva").strip()
    final_url = f"{img.image.url}#{size_fragment}-{align_fragment}"
    md  = f"\n\n![{alt}]({final_url})\n"

    m.content = (m.content or "")
    if m.content and not m.content.endswith("\n"):
        m.content += "\n"
    m.content += md
    m.save(update_fields=["content"])

    messages.success(request, "Kuva lisättiin sisältöön.")
    return redirect("material_detail", material_id=m.id)