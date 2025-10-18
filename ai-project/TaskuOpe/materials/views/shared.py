# materials/views/shared.py

from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe
import markdown as md
import re
import json
from urllib.parse import urlparse

from ..models import Material

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

def format_game_content_for_display(game_data):
    """
    Muotoilee pelin JSON-datan opettajalle helposti luettavaan muotoon.
    
    Args:
        game_data (dict): Pelin structured_content-data
        
    Returns:
        str: HTML/Markdown-muotoiltu, luettava versio pelin sisällöstä
    """
    if not game_data or not isinstance(game_data, dict):
        return "Ei pelisisältöä saatavilla."
    
    # MEMORY-PELI
    if 'pairs' in game_data:
        pairs = game_data.get('pairs', [])
        content = "## Muistipeli - Parit\n\n"
        content += f"**Parien määrä:** {len(pairs)}\n\n"
    
        if not pairs:
            content += "<p><em>Ei pareja saatavilla</em></p>"
            return content
    
        # Detect column headers dynamically from the first pair
        first_pair = pairs[0] if pairs else {}
    
        # Try to determine what kind of pairs these are
        col1_key = None
        col2_key = None
        col1_name = "Kysymys"
        col2_name = "Vastaus"
    
        # Check for common key patterns
        if 'suomi' in first_pair or 'Suomi' in first_pair:
            col1_key = 'suomi'
            col2_key = 'englanti'
            col1_name = "Suomi"
            col2_name = "Englanti"
        elif 'question' in first_pair:
            col1_key = 'question'
            col2_key = 'answer'
            col1_name = "Kysymys"
            col2_name = "Vastaus"
        elif 'word1' in first_pair:
            col1_key = 'word1'
            col2_key = 'word2'
            col1_name = "Kortti 1"
            col2_name = "Kortti 2"
        else:
            # Use the first two keys found
            keys = list(first_pair.keys())
            if len(keys) >= 2:
                col1_key = keys[0]
                col2_key = keys[1]
                col1_name = keys[0].capitalize()
                col2_name = keys[1].capitalize()
    
        content += '<table class="table table-striped">\n'
        content += f'<thead><tr><th>#</th><th>{col1_name}</th><th>{col2_name}</th></tr></thead>\n'
        content += '<tbody>\n'
    
        for i, pair in enumerate(pairs, 1):
            # Get values dynamically
            val1 = '?'
            val2 = '?'
        
            if col1_key:
                val1 = (pair.get(col1_key) or pair.get(col1_key.capitalize()) or 
                    pair.get('word1') or pair.get('fi') or pair.get('suomi') or '?')
                val2 = (pair.get(col2_key) or pair.get(col2_key.capitalize()) or 
                   pair.get('word2') or pair.get('en') or pair.get('englanti') or '?')
            else:
                # Fallback: take any two values from the dict
                values = list(pair.values())
                if len(values) >= 2:
                    val1 = values[0]
                    val2 = values[1]
        
            content += f'<tr><td>{i}</td><td>{val1}</td><td>{val2}</td></tr>\n'
    
        content += '</tbody>\n'
        content += '</table>\n'
        return content
    
    # VISA/QUIZ
    elif 'levels' in game_data:
        levels = game_data.get('levels', [])
        content = "## Tietovisa\n\n"
        content += f"**Tasojen määrä:** {len(levels)}\n\n"

        question_counter = 0

        for level_idx, level in enumerate(levels, 1):
            level_name = level.get('name', f'Taso {level_idx}')
            questions = level.get('questions', [])
    
            if not questions and 'question' in level:
                questions = [level]
    
            content += f"### {level_name}\n\n"
    
            if not questions or len(questions) == 0:
                content += "<p><em>Ei kysymyksiä tällä tasolla</em></p>\n\n"
                continue
    
            content += f"**Kysymyksiä:** {len(questions)}\n\n"
    
            for q_idx, question in enumerate(questions, 1):
                question_counter += 1
                q_text = question.get('question', '?')
        
            # Hae vastausvaihtoehdot eri nimillä
            options = (question.get('options') or 
                      question.get('answers') or 
                      question.get('choices') or [])
        
            # Hae oikea vastaus
            correct = question.get('correct', question.get('correctAnswer'))
        
            # Jos correct on numero (indeksi), muunna se tekstiksi
            correct_text = correct
            if isinstance(correct, int) and options and 0 <= correct < len(options):
                correct_text = options[correct]
            elif isinstance(correct, str) and correct.isdigit():
                # Jos correct on merkkijono "0", "1" jne
                idx = int(correct)
                if options and 0 <= idx < len(options):
                    correct_text = options[idx]
        
            content += '<div class="card mb-3">\n'
            content += '<div class="card-header bg-light">\n'
            content += f'<strong>Kysymys {question_counter}:</strong> {q_text}\n'
            content += '</div>\n'
            content += '<div class="card-body">\n'
        
            # Näytä vastausvaihtoehdot jos niitä on
            if options and len(options) > 0:
                content += '<p class="mb-2"><strong>Vastausvaihtoehdot:</strong></p>\n'
                content += '<ul class="list-group mb-3">\n'
                
                for opt_idx, option in enumerate(options):
                    # Tarkista onko tämä oikea vastaus (vertaa sekä indeksiin että tekstiin)
                    is_correct = (option == correct_text or 
                                 opt_idx == correct or 
                                 str(opt_idx) == str(correct))
                    
                    if is_correct:
                        content += f'<li class="list-group-item list-group-item-success">✅ <strong>{chr(65 + opt_idx)})</strong> {option} <span class="badge bg-success ms-2">OIKEA VASTAUS</span></li>\n'
                    else:
                        content += f'<li class="list-group-item"><strong>{chr(65 + opt_idx)})</strong> {option}</li>\n'
                
                content += '</ul>\n'
            else:
                content += '<p class="text-muted"><em>Ei vastausvaihtoehtoja saatavilla</em></p>\n'
            
            content += '</div>\n'
            content += '</div>\n'
    
        return content
    
    # Tuntematon pelityyppi
    else:
        try:
            formatted = json.dumps(game_data, indent=2, ensure_ascii=False)
            content = "## Pelin sisältö\n\n"
            content += "<details open><summary>JSON-data</summary>\n"
            content += f"<pre>{formatted}</pre>\n"
            content += "</details>"
            return content
        except:
            return f"## Pelin sisältö\n\n<pre>{str(game_data)}</pre>"

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

