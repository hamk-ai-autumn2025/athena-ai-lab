from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile 

import json
import os
import uuid
import base64
import requests
import re
from urllib.parse import urljoin

from ..models import Assignment, Submission, Material, MaterialImage
from ..ai_service import generate_speech, generate_image_bytes
from TaskuOpe.ops_chunks import get_facets, retrieve_chunks
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        # Määritä kysymysten määrä vaikeustason mukaan
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
        model="gpt-4o",
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
            model="gpt-4o",
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


# materials/views/api.py

@require_POST
def generate_image_view(request):
    """
    Käsittelee kuvapyynnöt AJAX:lla, tehostetulla lokituksella.
    """
    print("\n--- generate_image_view CALLED ---")
    print(f"Request Method: {request.method}")
    print(f"Content-Type: {request.content_type}")
    print(f"request.POST: {request.POST}")
    print(f"request.FILES: {request.FILES}")

    uploaded_file = request.FILES.get('image_upload')

    if uploaded_file:
        print(">>> FILE UPLOAD PATH <<<")
        # --- VAIHTOEHTO 1: Käyttäjä latasi tiedoston ---
        print(f"Uploaded file detected: {uploaded_file.name}, type: {uploaded_file.content_type}, size: {uploaded_file.size}")

        if not uploaded_file.content_type.startswith('image/'):
            print("ERROR: Uploaded file is not an image.")
            return JsonResponse({"error": "Vain kuvatiedostot sallitaan."}, status=400)

        rel_dir = "uploaded_images"
        filename = f"{uuid.uuid4().hex[:8]}_{uploaded_file.name}"
        file_path = os.path.join(rel_dir, filename)
        print(f"Saving file to path: {file_path}")

    else:
        print(">>> AI GENERATION PATH (or error) <<<")
        # --- VAIHTOEHTO 2: Käyttäjä generoi AI:lla ---
        prompt = ""
        payload = {} # Initialize payload
        if request.content_type and "application/json" in request.content_type:
            try:
                payload = json.loads((request.body or b"").decode("utf-8") or "{}")
                prompt = (payload.get("prompt") or "").strip()
                print(f"Prompt found in JSON body: '{prompt}'")
            except json.JSONDecodeError:
                print("JSON body detected but failed to parse.")
                pass

        if not prompt:
             prompt = (request.POST.get("prompt") or "").strip()
             if prompt:
                 print(f"Prompt found in POST data: '{prompt}'")

        if not prompt:
            print("ERROR: No file uploaded AND prompt is empty.")
            return JsonResponse({"error": "Tyhjä prompt tai ei ladattua tiedostoa."}, status=400)

        # Prompt was found, proceed with AI generation
        print("Proceeding with AI generation...")
        try:
            size = payload.get("size", "1024x1024")
            print(f"Generating image with prompt: '{prompt}', size: {size}")
            image_bytes = generate_image_bytes(prompt=prompt, size=size)
            if not image_bytes:
                print("ERROR: AI generation returned empty result.")
                return JsonResponse({"error": "Generointi palautti tyhjän tuloksen."}, status=502)
        except Exception as e:
            print(f"ERROR: AI generation failed: {e}")
            return JsonResponse({"error": str(e)}, status=502)

        rel_dir = "ai_images"
        filename = f"{uuid.uuid4().hex}.png"
        file_path = os.path.join(rel_dir, filename)
        uploaded_file = ContentFile(image_bytes, name=filename)
        print(f"AI image generated, saving to path: {file_path}")

    # --- YHTEINEN TALLENNUSLOGIIKKA ---
    try:
        print("Attempting to save file...")
        saved_path = default_storage.save(file_path, uploaded_file)
        image_url = default_storage.url(saved_path)
        print(f"File saved successfully! URL: {image_url}")
        return JsonResponse({"image_url": image_url}, status=201)

    except Exception as e:
        print(f"ERROR: File saving failed: {e}")
        return JsonResponse({"error": f"Tallennus epäonnistui: {str(e)}"}, status=500)
    finally:
        print("--- generate_image_view END ---")

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