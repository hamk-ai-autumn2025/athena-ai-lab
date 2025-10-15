# Standardikirjastot
import csv
import io
import json
import os
import re
import uuid
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

# Kolmannen osapuolen kirjastot
import markdown as md
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Django-moduulit
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Value
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST
from django.db.models.functions import Concat

# Omat sovellusmoduulit
from TaskuOpe.ops_chunks import get_facets, retrieve_chunks
from users.models import CustomUser

from .ai_rubric import create_or_update_ai_grade
from .ai_service import ask_llm, ask_llm_with_ops, generate_image_bytes, generate_speech
from .forms import AddImageForm, AssignForm, AssignmentForm, GradingForm, MaterialForm, SubmissionForm
from .models import AIGrade, Assignment, Material, MaterialImage, Rubric, Submission
from .plagiarism import build_or_update_report

# Tarkista, onko OpenAI-kirjasto saatavilla
try:
    from openai import OpenAI
    _has_openai = True
except Exception:
    _has_openai = False


# ================= Pelin luontia varte ====================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# ==========================================================

# Pelisisältö
def generate_game_content(topic: str, game_type: str, difficulty: str = 'medium') -> dict:
    """
    Generoi pelisisällön tekoälyllä annetun aiheen, pelityypin ja
    vaikeustason perusteella.

    Args:
        topic (str): Pelin aihe tai kuvaus.
        game_type (str): Pelityyppi ('quiz', 'hangman', 'memory').
        difficulty (str): Vaikeustaso ('easy', 'medium', 'hard')
                          (käytössä vain visapelissä).

    Returns:
        dict: Generoitu pelisisältö JSON-muodossa.

    Raises:
        ValueError: Jos annettua pelityyppiä ei tunnisteta.
    """
    prompt = ""
    
    if game_type == 'quiz':
        # 🆕 Määritä kysymysten määrä vaikeustason mukaan
        question_counts = {
            'easy': 5,
            'medium': 10,
            'hard': 15
        }
        num_questions = question_counts.get(difficulty, 10)
        
        prompt = f"""
Rooli: Toimi suomalaisena opettajana ja tietokirjailijana.
Tehtävä: Laadi TARKALLEEN {num_questions} laadukasta monivalintakysymystä.
Aihe: "{topic}"
Vaikeustaso: alakoulu
Säännöt:
1. Faktojen on oltava oikein.
2. Kysymysten on oltava selkeitä ja yksiselitteisiä.
3. Vastausvaihtoehdoista vain yksi saa olla oikein.
4. Varmista, että JSON-objektin `correct`-indeksi vastaa oikean vastauksen paikkaa `choices`-taulukossa.
Vastauksen muoto:
- Palauta VAIN JSON-objekti.
- Kaikki tekstit suomeksi.
- Noudata tarkasti tätä rakennetta: {{"difficulty":"{difficulty}","levels":[...]}}
"""
    elif game_type == 'hangman':
        # Hirsipuu - 30 sanaa
        prompt = f"""
Toimi suomenkielisenä opettajana. Anna TARKALLEEN 30 suomenkielistä sanaa aiheesta "{topic}" hirsipuupeliin.
Säännöt:
1. Jokainen sana on aiheeseen sopiva
2. Vain kirjaimia (A-Ö), 4-12 merkkiä pitkä
3. Yleiskielisiä sanoja, ei ammattislangia
4. Vaihteleva vaikeustaso (helpoista haastaviin)
5. Ei toistoa

Palauta VAIN JSON-muodossa: {{"topic":"{topic}","words":["sana1","sana2",...,"sana30"]}}

Aihe: {topic}
"""
    elif game_type == 'memory':
        # Muistipeli - 10 paria
        prompt = f"""
Toimi suomenkielisenä opettajana. Laadi TÄSMÄLLEEN 10 muistipelikorttiparia aiheesta.
AIHE: {topic}
KRIITTISET SÄÄNNÖT:
1. JOKAISEN VASTAUKSEN ON OLTAVA UNIIKKI.
2. JOKAISEN KYSYMYKSEN ON OLTAVA UNIIKKI.
3. Tekstit lyhyitä (max 15 merkkiä).
Palauta VAIN JSON: {{"pairs":[...]}}
"""
    else:
        raise ValueError("Tuntematon pelityyppi")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.choices[0].message.content
    return json.loads(content)

# Pelin metadata
def generate_game_metadata(game_name: str, topic: str) -> dict:
    """
    Generoi pelille otsikon ja aiheen OpenAI:n avulla.
    Aihe valitaan Suomen opetussuunnitelman mukaisista oppiaineista.

    Args:
        game_name (str): Pelin nimi tai tyyppi (esim. 'Quiz').
        topic (str): Pelin aihe tai kuvaus.

    Returns:
        dict: Sanakirja, joka sisältää generoidun otsikon ('title')
              ja oppiaineen ('subject').
    """
    
    # Suomen opetussuunnitelman mukaiset oppiaineet
    VALID_SUBJECTS = [
        "Äidinkieli ja kirjallisuus",
        "Matematiikka",
        "Ympäristöoppi",
        "Ruotsi",
        "Englanti",
        "Fysiikka",
        "Kemia",
        "Maantieto",
        "Kotitalous",
        "Terveystieto",
        "Liikunta",
        "Musiikki",
        "Kuvataide",
        "Käsityö",
        "Uskonto tai elämänkatsomustieto",
        "Historia",
        "Yhteiskuntaoppi"
    ]
    
    subjects_list = "\n".join([f"- {s}" for s in VALID_SUBJECTS])
    
    prompt = f"""Sinulle annetaan aihe pelille ja pelityyppi.
Tehtäväsi on luoda:
1. Lyhyt, houkutteleva otsikko pelille (max 20 merkkiä)
2. Oppiaine Suomen perusopetuksen opetussuunnitelman mukaan

Pelityyppi: {game_name}
Aihe/kuvaus: {topic}

TÄRKEÄÄ:
- Otsikon tulee olla innostava ja selkeä
- Aihealue TULEE valita VAIN seuraavista Suomen opetussuunnitelman oppiaineista:
{subjects_list}
- Valitse oppiaine sen mukaan, mikä parhaiten vastaa pelin aihetta
- Jos peli ei sovi mihinkään tiettyyn oppiaineeseen, valitse "Ympäristöoppi" yleiseksi aihealueeksi
- Palauta VAIN JSON-muodossa

Palauta täsmälleen tässä muodossa:
{{"title":"otsikko tähän","subject":"oppiaine tähän"}}
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # Varmista että palautettu oppiaine on listalla
        returned_subject = result.get('subject', 'Ympäristöoppi')
        if returned_subject not in VALID_SUBJECTS:
            returned_subject = 'Ympäristöoppi'
        
        return {
            'title': result.get('title', f'{game_name.capitalize()}: {topic[:40]}'),
            'subject': returned_subject
        }
    except Exception as e:
        # Fallback jos API-kutsu epäonnistuu
        return {
            'title': f'{game_name.capitalize()}: {topic[:40]}',
            'subject': 'Ympäristöoppi'
        }

# --- Main Dashboard ---
@login_required(login_url='kirjaudu')
def dashboard_view(request):
    """
    Renderöi oikeanlaisen hallintapaneelin käyttäjän roolin mukaan.
    Opettajille näytetään heidän materiaalit ja tehtävänannot.
    Oppilaille näytetään heidän tehtäviensä tilanne.

    Args:
        request: HTTP-pyyntö.

    Returns:
        HttpResponse: Renderöity hallintapaneelin sivu.
    """
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
    
        # Suodata pois suoritetut pelit etusivulta
        qs_for_display = qs.exclude(
        status='GRADED',
        material__material_type='peli'
        )

        counts = {
        "assigned": qs_for_display.filter(status=Assignment.Status.ASSIGNED).count(),
        "in_progress": qs_for_display.filter(status=Assignment.Status.IN_PROGRESS).count(),
        "graded": qs_for_display.filter(status=Assignment.Status.GRADED).count(),
        }

        due_soon = (
        qs_for_display
        .exclude(due_at__isnull=True)
        .filter(due_at__gte=timezone.now())
        .order_by('due_at')[:3]
        )

        return render(request, 'dashboard/student.html', {
        "counts": counts,
        "due_soon": due_soon,
        })

    return redirect('kirjaudu')

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
    all_materials = Material.objects.filter(author=request.user).order_by('-created_at')
    
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
                        material.structured_content = json.loads(json_data_str)
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

@require_POST
@login_required
def generate_game_ajax_view(request):
    """
    AJAX-näkymä pelisisällön ja metadatan generointiin tekoälyllä.
    Vain opettajat voivat käyttää tätä.

    Args:
        request: HTTP-pyyntö, sisältää aiheen, pelityypin ja vaikeustason.

    Returns:
        JsonResponse: Sisältää generoidun pelidatan ja metadatan
                      tai virheilmoituksen.
    """
    if not hasattr(request.user, "role") or request.user.role != "TEACHER":
        return JsonResponse({'error': 'Vain opettajat voivat luoda pelejä.'}, status=403)
    
    try:
        data = json.loads(request.body)
        topic = data.get('topic')
        game_type = data.get('game_type')
        difficulty = data.get('difficulty', 'medium')  # 🆕 Oletuksena medium
        
        if not topic or not game_type:
            return JsonResponse({'error': 'Aihe ja pelityyppi ovat pakollisia.'}, status=400)

        # Generoi pelisisältö vaikeustasolla
        game_data = generate_game_content(topic, game_type, difficulty)
        
        # Generoi otsikko ja aihe automaattisesti
        metadata = generate_game_metadata(topic, game_type)
        
        # Palauta sekä pelisisältö että metadata
        return JsonResponse({
            'success': True, 
            'game_data': game_data,
            'metadata': metadata
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@require_POST
@login_required
def complete_game_ajax_view(request, assignment_id):
    """
    AJAX-näkymä pelin suorituksen tilan tallentamiseen ja pisteytykseen.
    Käyttäjältä odotetaan pelin pistemäärää. Tehtävän status päivitetään
    ja uusi palautus luodaan tai olemassa olevaa päivitetään.

    Args:
        request: HTTP-pyyntö, sisältää pelin pistemäärän.
        assignment_id (uuid.UUID): Suoritetun tehtävän ID.

    Returns:
        JsonResponse: Sisältää suorituksen tilan, pistemäärän ja
                      tiedon onnistumisesta.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id, student=request.user)

    # Määritä pelityyppi
    try:
        game_data = assignment.material.structured_content or {}
    except (AttributeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Virheellinen pelisisältö'}, status=400)

    if 'levels' in game_data:
        game_type = 'quiz'
    elif 'word' in game_data or 'words' in game_data:  # Lisätty words-tuki
        game_type = 'hangman'
    elif 'pairs' in game_data:
        game_type = 'memory'
    else:
        return JsonResponse({'status': 'error', 'message': 'Tuntematon pelityyppi'}, status=400)

    # Lue pisteet
    try:
        data = json.loads(request.body)
        score = data.get('score', 0)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Virheellinen JSON'}, status=400)

    # Jos peli on jo suoritettu
    if assignment.status == Assignment.Status.GRADED:
        if game_type == 'quiz':
            existing_sub = assignment.submissions.last()
            if existing_sub and existing_sub.score and existing_sub.score >= 80:
                return JsonResponse({
                    'status': 'already_completed',
                    'completed': True,
                    'score': existing_sub.score
                })
            
            if not existing_sub or (existing_sub.score or 0) < score:
                if existing_sub:
                    existing_sub.score = score
                    existing_sub.save(update_fields=['score'])
                else:
                    Submission.objects.create(
                        assignment=assignment,
                        student=request.user,
                        status=Submission.Status.SUBMITTED,
                        submitted_at=timezone.now(),
                        graded_at=timezone.now(),
                        score=score,
                        feedback="Peli suoritettu."
                    )
            
            if score >= 80:
                assignment.status = Assignment.Status.GRADED
                assignment.save(update_fields=['status'])
                return JsonResponse({
                    'status': 'success',
                    'score': score,
                    'completed': True
                })
            else:
                return JsonResponse({
                    'status': 'retry',
                    'score': score,
                    'completed': False
                })
        else:
            existing_sub = assignment.submissions.last()
            return JsonResponse({
                'status': 'already_completed',
                'completed': True,
                'score': existing_sub.score if existing_sub else 0
            })

    # Ensimmäinen yritys
    if game_type == 'quiz':
        if score >= 80:
            assignment.status = Assignment.Status.GRADED
            assignment.save(update_fields=['status'])
            completed = True
        else:
            completed = False
    else:
        assignment.status = Assignment.Status.GRADED
        assignment.save(update_fields=['status'])
        completed = True

    # Luo submission
    Submission.objects.create(
        assignment=assignment,
        student=request.user,
        status=Submission.Status.SUBMITTED,
        submitted_at=timezone.now(),
        graded_at=timezone.now(),
        score=score,
        feedback="Peli suoritettu."
    )

    # TÄRKEÄ DEBUG: Tulosta konsoliin
    print(f"[GAME COMPLETION] Student: {request.user.username}, Score: {score}, Completed: {completed}")

    return JsonResponse({
        'status': 'success',
        'score': score,
        'completed': completed
    })

# --- Assignments ---
@login_required(login_url='kirjaudu')
def assign_material_view(request, material_id):
    """
    Jakaa materiaalin opiskelijoille.
    HUOM: Tämä funktio on kaksoiskappale alempana olevan kanssa.
          Tätä voi siistiä ja yhdistää myöhemmin.

    Args:
        request: HTTP-pyyntö.
        material_id (uuid.UUID): Jaettavan materiaalin ID.

    Returns:
        HttpResponse: Renderöity tehtävänantosivu tai ohjaus
                      hallintapaneeliin.
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
                assignment, created = Assignment.objects.get_or_create(
                    material=material,
                    student=student,
                    defaults={'assigned_by': request.user, 'due_at': due_at}
                )
                if created:
                    count += 1
            messages.success(request, f"Materiaali on onnistuneesti jaettu {count} opiskelijalle.")
            return redirect('dashboard')
    else:
        form = AssignmentForm()
    return render(request, "assignments/assign.html", {"material": m, "form": form})


# materials/views.py

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

@login_required(login_url='kirjaudu')
@require_POST
def assignment_autosave_view(request, assignment_id):
    """
    Tallentaa tehtävän luonnoksen taustalla (AJAX).

    Palauttaa JSON-vastauksen, joka ilmaisee tallennuksen onnistumisen
    ja tallennushetken.

    Käytetään fetch()-kutsulla 'assignments/detail.html' -sivulla
    tehtävän vastausluonnoksen automaattiseen tallennukseen.

    Args:
        request: HttpRequest-objekti.
        assignment_id (int): Tehtävän yksilöivä ID.

    Returns:
        JsonResponse: JSON-objekti, joka sisältää 'ok' (bool) ja
                      mahdollisesti 'error' (str) tai 'saved_at' (str).
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

# --- Deletion ---
@login_required(login_url='kirjaudu')
def delete_material_view(request, material_id):
    """
    Poistaa opettajan luoman materiaalin.

    Varmistaa, että materiaali kuuluu pyynnön tehneelle opettajalle.
    Hyväksyy vain POST-pyynnöt.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Poistettavan materiaalin yksilöivä ID.

    Returns:
        HttpResponse: Uudelleenohjaus 'dashboard'-sivulle onnistuneen
                      poiston jälkeen, tai virhesivu jos HTTP-metodi
                      ei ole POST.
    """
    material = get_object_or_404(Material, id=material_id, author=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    title = material.title
    material.delete()
    messages.success(request, f"Materiaali '{title}' poistettu.")
    return redirect('dashboard')


@login_required(login_url='kirjaudu')
def delete_assignment_view(request, assignment_id):
    """
    Poistaa opettajan luoman tehtävänannon.

    Varmistaa, että tehtävänanto kuuluu pyynnön tehneelle opettajalle.
    Hyväksyy vain POST-pyynnöt.

    Args:
        request: HttpRequest-objekti.
        assignment_id (int): Poistettavan tehtävänannon yksilöivä ID.

    Returns:
        HttpResponse: Uudelleenohjaus 'dashboard'-sivulle onnistuneen
                      poiston jälkeen, tai virhesivu jos HTTP-metodi
                      ei ole POST.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id, assigned_by=request.user)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    assignment.delete()
    messages.success(request, "Tehtävänanto poistettu.")
    return redirect('dashboard')

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
def add_material_image_view(request, material_id):
    """
    Käsittelee kuvan lisäämisen materiaaliin joko lataamalla tiedoston
    tai generoimalla kuvan tekoälyllä.

    Kuva lisätään materiaalin sisältöön Markdown-muodossa ja
    tallennetaan MaterialImage-objektina.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Materiaalin yksilöivä ID, johon kuva lisätään.

    Returns:
        HttpResponse: Renderöity HTML-sivu kuvanlisäyslomakkeella tai
                      uudelleenohjaus onnistuneen lisäyksen jälkeen.
                      Uudelleenohjaa myös, jos käyttäjällä ei ole oikeuksia.
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
            size_fragment = form.cleaned_data.get("size")
            alignment = form.cleaned_data.get("alignment")
            
            def append_image_to_content(image_url: str, cap: str, size_frag: str, align_frag: str):
                final_url = f"{image_url}#{size_frag}-{align_frag}"
                md_img = f"![{cap or 'Kuva'}]({final_url})"
                m.content = (m.content or "").rstrip() + f"\n\n{md_img}\n"
                m.save(update_fields=["content"])

            # Tapaus 1: Käyttäjä latasi tiedoston
            if upload:
                mi = MaterialImage.objects.create(material=m, image=upload, caption=caption, created_by=request.user)
                append_image_to_content(mi.image.url, caption, size_fragment, align_fragment)
                messages.success(request, "Ladattu kuva lisätty sisältöön.")
                return redirect("material_detail", material_id=m.id)

            # Tapaus 2: Käyttäjä generoi kuvan
            if prompt:
                try:
                    image_data = generate_image_bytes(prompt, size="1024x1024")
                    if not image_data:
                        messages.error(request, "Kuvan generointi ei palauttanut dataa (tarkista API-avain).")
                    else:
                        mi = MaterialImage.objects.create(
                            material=m,
                            image=ContentFile(image_data, name="gen.png"),
                            caption=caption,
                            created_by=request.user,
                        )
                        append_image_to_content(mi.image.url, caption, size_fragment, align_fragment)
                        messages.success(request, "Generoitu kuva lisätty sisältöön.")
                        return redirect("material_detail", material_id=m.id)
                except Exception as e:
                    messages.error(request, f"Kuvan generointi epäonnistui: {e}")
                
                # Ohjataan takaisin, jos generointi epäonnistui tai ei palauttanut dataa
                return redirect("material_add_image", material_id=m.id)

    # GET-pyyntö tai virheellinen POST
    else:
        form = AddImageForm()

    return render(request, "materials/add_image.html", {"material": m, "form": form})


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

@login_required
def unassign_view(request, assignment_id):
    """
    Poistaa tietyn tehtävänannon (Assignment) opiskelijalta.

    Varmistaa, että käyttäjä on opettaja ja on luonut kyseisen tehtävänannon.
    Tämä toiminto poistaa koko Assignment-objektin tietokannasta.

    Args:
        request: HttpRequest-objekti.
        assignment_id (int): Poistettavan tehtävänannon yksilöivä ID.

    Returns:
        HttpResponse: Uudelleenohjaus 'view_submissions'-sivulle onnistuneen
                      poiston jälkeen, tai jos käyttäjällä ei ole oikeuksia.
    """
    a = get_object_or_404(Assignment, pk=assignment_id)
    if request.user.role != "TEACHER" or a.assigned_by_id != request.user.id:
        messages.error(request, "Ei oikeutta.")
        return redirect("view_submissions", material_id=a.material_id)
    a.delete()
    messages.success(request, "Tehtävänanto poistettu tältä oppilaalta.")
    return redirect("view_submissions", material_id=a.material_id)

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

@require_POST
def generate_image_view(request):
    """
    Generoi kuvan tekoälyllä annetun promptin perusteella ja tallentaa sen.

    Hyväksyy vain POST-pyynnöt. Ottaa vastaan JSON- tai form-dataa.
    Palauttaa generoidun kuvan URL-osoitteen.

    Args:
        request: HttpRequest-objekti, sisältäen "prompt"-parametrin.

    Returns:
        JsonResponse: JSON-objekti, joka sisältää "image_url"-kentän
                      onnistuneen generoinnin jälkeen (HTTP 201), tai
                      "error"-kentän virheen sattuessa (HTTP 400, 502).
    """
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
    """
    Näyttää yksittäisen materiaalin yksityiskohdat.

    Hakee materiaalin ID:n perusteella, renderöi sen sisällön HTML:ksi
    ja välittää tiedot mallipohjalle.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Näytettävän materiaalin yksilöivä ID.

    Returns:
        HttpResponse: Renderöity HTML-sivu, joka näyttää materiaalin tiedot
                      ja renderöidyn sisällön.
    """
    material = get_object_or_404(Material, pk=material_id)

    rendered_content = render_material_content_to_html(material.content)
    
    return render(request, "materials/material_detail.html", {
        "material": material,
        "rendered_content": rendered_content,
    })


@login_required
@require_POST
def delete_material_image_view(request, image_id):
    """
    Poistaa materiaaliin liitetyn kuvan.

    Varmistaa, että käyttäjä on opettaja ja materiaalin tekijä.
    Hyväksyy vain POST-pyynnöt poistotoiminnolle.
    Kuvan tiedosto poistetaan levyltä Django-signaalin avulla.

    Args:
        request: HttpRequest-objekti.
        image_id (int): Poistettavan MaterialImage-objektin yksilöivä ID.

    Returns:
        HttpResponse: Uudelleenohjaus 'material_detail'-sivulle onnistuneen
                      poiston jälkeen, tai HttpResponseForbidden, jos käyttäjällä
                      ei ole oikeuksia.
    """
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
    """
    Lisää valitun galleriakuvan Markdown-tagina materiaalin sisältökenttään.

    Kuvan koko ja sijainti sisällössä määräytyvät POST-datasta.
    Varmistaa, että käyttäjä on opettaja ja materiaalin tekijä.
    Hyväksyy vain POST-pyynnöt.

    Args:
        request: HttpRequest-objekti.
        material_id (int): Materiaalin yksilöivä ID, johon kuva lisätään.
        image_id (int): Lisättävän MaterialImage-objektin yksilöivä ID.

    Returns:
        HttpResponse: Uudelleenohjaus 'material_detail'-sivulle onnistuneen
                      lisäyksen jälkeen, tai jos käyttäjällä ei ole oikeuksia.
    """
   
    m = get_object_or_404(Material, pk=material_id)
    if request.user.role != "TEACHER" or m.author_id != request.user.id:
        messages.error(request, "Ei oikeutta muokata tämän materiaalin sisältöä.")
        return redirect("material_detail", material_id=m.id)

    img = get_object_or_404(MaterialImage, pk=image_id, material=m)
    
    # Lue koko POST-datasta, oletuksena keskikokoinen
    size_fragment = request.POST.get(f'size_{image_id}', 'size-md')
    align_fragment = request.POST.get(f'align_{image_id}', 'align-center')

    alt = (img.caption or "Kuva").strip()
    # Yhdistetään tiedot fragmenttiin
    final_url = f"{img.image.url}#{size_fragment}-{align_fragment}"
    md  = f"\n\n![{alt}]({final_url})\n"

    m.content = (m.content or "")
    if m.content and not m.content.endswith("\n"):
        m.content += "\n"
    m.content += md
    m.save(update_fields=["content"])

    messages.success(request, "Kuva lisättiin sisältöön.")
    return redirect("material_detail", material_id=m.id)

@require_POST
def generate_image_view(request):
    """
    Generoi kuvan tekoälyllä annetun promptin perusteella, muokkaa sen
    haluttuun kokoon ja tallentaa sen.
    """
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

# Päivitä render_material_content_to_html-funktio
_MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

_MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def render_material_content_to_html(text: str) -> str:
    """
    Muuntaa Markdown-tekstin HTML:ksi.
    """
    if not text:
        return ""

    def replace_custom_image_syntax(match):
        alt_text = match.group(1)
        url = match.group(2)
        parsed_url = urlparse(url)
        path = parsed_url.path
        fragment = parsed_url.fragment
        size_match = re.search(r'size-(sm|md|lg)', fragment)
        align_match = re.search(r'align-(left|center|right)', fragment)
        size_class = size_match.group(0) if size_match else "size-md"
        align_class = align_match.group(0) if align_match else "align-center"
        img_tag = f'<img src="{path}" alt="{alt_text}" class="img-fluid rounded border my-3 img-scaled {size_class}">'
        return f'<div class="image-wrapper {align_class}">{img_tag}</div>'

    def preprocess_custom_blocks(text_content):
        # Etsitään kaikki :::note ... ::: -lohkot
        pattern = re.compile(r':::[ ]?note\n(.*?)\n:::', re.DOTALL)
        # Korvataan ne HTML-elementillä, jolla on oma CSS-luokka
        return pattern.sub(r'<p class="custom-block note">\1</p>', text_content)

    # 1. Esikäsitellään kustomoidut kuvat
    processed_text = _MD_IMG_RE.sub(replace_custom_image_syntax, text)
    # 2. Esikäsitellään uudet tekstityylit
    processed_text = preprocess_custom_blocks(processed_text)
    
    # 3. Annetaan Markdown-kirjaston hoitaa loput
    html = md.markdown(processed_text, extensions=['extra'])
    return mark_safe(html)

@login_required
def teacher_student_list_view(request):
    """
    Käsittelee opiskelijatietojen näyttämistä ja päivittämistä opettajille.

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

# Text-to-Speech for assignment content -> Poistetaan ym regexillä
@login_required(login_url='kirjaudu')
@require_POST
def assignment_tts_view(request, assignment_id):
    """
    Generoi äänitiedoston tehtävänannon sisällöstä (ilman kuvatekstejä) ja palauttaa sen.

    Vaatii käyttäjän kirjautumisen ja POST-pyynnön.
    Tarkistaa, että käyttäjä on tehtävän omistaja.
    Poistaa Markdown-kuvat tehtävän sisällöstä ennen äänitiedoston luontia.
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if assignment.student != request.user:
        return HttpResponseForbidden("Sinulla ei ole oikeuksia tähän.")

    raw_text = assignment.material.content
    if not raw_text:
        return JsonResponse({"Virhe": "Ei sisältöä luettavaksi."}, status=400)

    # === KORJATTU SÄÄNNÖLLINEN LAUSEKE ===
    # Tämä on tarkempi ja poistaa vain oikeat Markdown-kuvat.
    clean_text = re.sub(r'!\[[^\]]*\]\([^\)]*\)\s*', '', raw_text)

    # Varmistetaan, että tekstiä jäi jäljelle siivouksen jälkeen
    if not clean_text.strip():
        # Jos jäljelle jäi vain tyhjää, palautetaan virhe.
        return JsonResponse({"Virhe": "Ei luettavaa tekstiä löytynyt siivouksen jälkeen."}, status=400)

    audio_bytes = generate_speech(clean_text)

    if audio_bytes:
        return HttpResponse(audio_bytes, content_type='audio/mpeg')
    else:
        return JsonResponse({"Virhe": "Äänitiedoston luonti epäonnistui."}, status=500)
    
#JSON Chunks lataus tekoälylle
@require_GET
def ops_facets(request):
    return JsonResponse(get_facets())

@require_GET
def ops_search(request):
    """
    Palauttaa JSON-muodossa saatavilla olevat fasettitiedot (esim. aiheet, luokka-asteet).

    Vaatii GET-pyynnön.
    """
    q = request.GET.get("q", "")
    try:
        k = int(request.GET.get("k", "8") or 8)
    except ValueError:
        k = 8
    subjects = request.GET.getlist("subject")  # voi toistua
    grades   = request.GET.getlist("grade")
    ctypes   = request.GET.getlist("ctype")
    results = retrieve_chunks(q, k=k, subjects=subjects, grades=grades, ctypes=ctypes)
    return JsonResponse({"results": results})