"""
Moduuli plagioinnin ja tekoälyn käytön analysointiin opiskelijapalautuksissa.

Käyttää OpenAI GPT-mallia arvioimaan palautusten alkuperäisyyttä ja
mahdollista tekoälyn tuottamaa sisältöä.
"""

from __future__ import annotations

import html
import json
import os
import re
from typing import Dict, List, Tuple

from django.db import transaction
from django.utils import timezone

# --- OpenAI SDK (v1.x) ---
try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError("Asenna OpenAI-kirjasto: pip install openai>=1.0.0") from e

# --- Kevyt TF-IDF vain verrokkien hakuun (retrieval). Varsinaisen arvion tekee LLM. ---
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError as e:
    raise ImportError("Asenna scikit-learn: pip install scikit-learn") from e

from .models import PlagiarismReport, Submission

# Alusta OpenAI-asiakas
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# Kuinka monta sisäistä verrokkia annetaan mallille luettavaksi
TOP_K = 3
# TF-IDF minimiraja verrokeille; alle tämän ei tarjota LLM:lle melun vähentämiseksi
RETRIEVAL_MIN_SIM = 0.15


def _get_internal_candidates(new: Submission, top_k: int = TOP_K) -> List[Tuple[Submission, float]]:
    """
    Palauttaa listan (Submission, similarity) saman tehtävän aiemmista palautuksista,
    rankattuna TF-IDF kosini-samankaltaisuuden mukaan. Käytetään vain LLM:n tukiverrokeiksi.

    Args:
        new (Submission): Uusi palautus, jota verrataan.
        top_k (int): Kuinka monta samankaltaisinta verrokkia palautetaan.

    Returns:
        List[Tuple[Submission, float]]: Lista tupleja, joissa on palautusobjekti ja
                                         sen samankaltaisuusarvo (0.0-1.0).
    """
    # Hae kaikki saman tehtävän aiemmat palautukset paitsi käsiteltävä palautus itse
    qs = Submission.objects.filter(assignment=new.assignment).exclude(id=new.id)
    past = list(qs)
    if not past:
        return []

    student_text = (new.response or "").strip()
    # Muodosta korpus TF-IDF:ää varten: uusi palautus ja kaikki aiemmat palautukset
    corpus = [student_text] + [(p.response or "") for p in past]

    # Alusta ja sovita TF-IDF-vektorisoija korpukseen
    vec = TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 3), min_df=1).fit(corpus)
    # Muunna tekstit vektoreiksi
    X = vec.transform(corpus)
    # Laske kosini-samankaltaisuus uuden palautuksen ja muiden välillä
    sims = cosine_similarity(X[0], X[1:])[0]
    # Järjestä verrokit samankaltaisuuden mukaan laskevasti
    ranked = sorted(enumerate(sims), key=lambda t: t[1], reverse=True)

    out: List[Tuple[Submission, float]] = []
    for idx, sc in ranked[:top_k]:
        # Lisää verrokki listaan vain, jos samankaltaisuus ylittää minimirajan
        if sc >= RETRIEVAL_MIN_SIM:
            out.append((past[idx], float(sc)))
    return out


def _build_prompt_payload(sub: Submission, cands: List[Tuple[Submission, float]]) -> dict:
    """
    Muodostaa tiiviin JSON-payloadin OpenAI-mallille.

    Args:
        sub (Submission): Opiskelijan palautus, jota arvioidaan.
        cands (List[Tuple[Submission, float]]): Lista sisäisistä verrokkipalautuksista
                                                 ja niiden samankaltaisuusarvoista.

    Returns:
        dict: JSON-muotoinen sanakirja, joka lähetetään LLM:lle.
    """
    return {
        "task": "originality_and_ai_use_assessment",
        "instructions_fi": (
            "Tee opettajalle alkuperäisyysraportti suomeksi. Arvioi kaksi asiaa:\n"
            "1) Kuinka todennäköisesti vastaus on LLM-tekoälyn (esim. ChatGPT) tuottama?\n"
            "2) Onko vastaus mahdollisesti plagioitu sisäisistä verrokeista (alla), ja mistä kohdista?\n"
            "Perustele lyhyesti. Palauta vain JSON. Skaalat 0.0..1.0."
        ),
        "scales": {
            "ai_generated_likelihood": "0.0..1.0 (0=ihmiseltä, 1=selvästi LLM)",
            "plagiarism_risk": "0.0..1.0 (0=ei viitteitä, 1=selvä plagiointi)"
        },
        "student_answer": sub.response or "",
        "internal_candidates": [
            {
                "submission_id": str(s.id),
                "student_hint": getattr(s.student, "username", None),
                "similarity_hint": sim,  # TF-IDF cosine vihje mallille (vain suuntaa antava)
                "text": s.response or ""
            }
            for s, sim in cands
        ]
    }


def _call_openai(payload: dict) -> dict:
    """
    Kutsuu GPT-4o-miniä OpenAI API:n kautta ja palauttaa parsitun JSON-vastauksen.

    Args:
        payload (dict): JSON-muotoinen sanakirja, joka sisältää mallille lähetettävät tiedot.

    Returns:
        dict: Parsittu JSON-vastaus OpenAI-mallilta.
    """
    system = (
        "Toimi suomalaisena akateemisen integriteetin avustajana. "
        "Ole varovainen: yksittäinen heuristiikka ei riitä. "
        "Palauta täsmälleen JSON-objekti ilman vapaata tekstiä ympärillä."
    )
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Jos malli palauttaa koodiaitauksen, yritä siivota kevyesti
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(\w+)?", "", cleaned).rstrip("`").strip()
        return json.loads(cleaned)


def _render_highlights_html(student_text: str, evidence: List[Dict]) -> str:
    """
    Rakentaa HTML-merkkijonon LLM:n antamista sitaateista/huomioista
    ja opiskelijan tekstistä.

    Args:
        student_text (str): Opiskelijan alkuperäinen vastausteksti.
                            Oletetaan, että tämä voi sisältää jo HTML-muotoilua (esim. piirroksia).
        evidence (List[Dict]): LLM:n antama lista todisteista/huomioista.

    Returns:
        str: HTML-muotoinen merkkijono, joka sisältää huomiot ja opiskelijan tekstin.
    """
    parts: List[str] = []
    parts.append("<div><em>LLM-raportin huomiot ja otteet:</em></div>")
    for ev in evidence or []:
        quote = (ev.get("quote") or "").strip()
        why = (ev.get("why") or "").strip()
        if quote:
            parts.append(
                '<blockquote style="margin:0 0 .5rem 0;border-left:3px solid #ccc;padding-left:.5rem;">'
                f'{html.escape(quote)}</blockquote>' # Escapoi sitaatti, koska se on LLM:n tuottamaa tekstiä
            )
        if why:
            parts.append(f'<div style="margin-bottom:.75rem;"><small>{html.escape(why)}</small></div>') # Escapoi selitys
    parts.append('<hr><div style="white-space:pre-wrap;">')
    # TÄRKEIN MUUTOS TÄSSÄ: Poista html.escape() student_text-kentän ympäriltä
    parts.append(student_text or "") # <-- MUUTA TÄMÄ RIVI
    parts.append("</div>")
    return "".join(parts)


def analyze_plagiarism(new_submission: Submission) -> Dict[str, object]:
    """
    Suorittaa tekoälypohjaisen plagioinnin ja tekoälyn käytön analyysin
    uudelle opiskelijapalautukselle.

    Args:
        new_submission (Submission): Uusi opiskelijapalautus, joka analysoidaan.

    Returns:
        Dict[str, object]: Sanakirja, joka sisältää analyysin tulokset:
                           - "best_submission": Mahdollisesti plagioitu lähdepalautus (Submission-objekti).
                           - "best_score": Plagiointiriski (float 0.0-1.0).
                           - "highlight_html": HTML-muotoinen yhteenveto ja korostukset.
                           - "notes": Lisätietoja analyysistä (esim. AI-todennäköisyys).
    """
    student_text = (new_submission.response or "").strip()
    if not student_text:
        return {
            "best_submission": None,
            "best_score": 0.0,
            "highlight_html": "Vastaus on tyhjä.",
            "notes": {"reason": "empty_response"},
        }

    # 1) Hae top-k sisäiset verrokit (vain LLM:n tueksi)
    candidates = _get_internal_candidates(new_submission, top_k=TOP_K)
    payload = _build_prompt_payload(new_submission, candidates)

    # 2) Pyydä arvio LLM:ltä
    data = _call_openai(payload)

    # Käsittele ja rajoita LLM:n antamat arvot välille 0.0-1.0
    ai_like = float(max(0.0, min(1.0, data.get("ai_generated_likelihood", 0.0))))
    plag_risk = float(max(0.0, min(1.0, data.get("plagiarism_risk", 0.0))))

    suspected = None
    for item in data.get("suspected_sources", []) or []:
        sid = (item.get("submission_id") or "").strip()
        if not sid:
            continue
        try:
            suspected = Submission.objects.get(id=sid)
            break
        except Submission.DoesNotExist:
            continue

    summary = (data.get("summary_fi") or "").strip()
    evidence = data.get("evidence_highlights", []) or []

    # Rakenna HTML-lohko raporttia varten
    html_block: List[str] = []
    html_block.append("<div><strong>LLM-yhteenveto:</strong> ")
    html_block.append(html.escape(summary) if summary else "—")
    html_block.append("</div>")
    html_block.append("<div><small>")
    html_block.append(f"LLM-arvio: AI-todennäköisyys = {ai_like:.2f}, plagiointiriski = {plag_risk:.2f}")
    html_block.append("</small></div>")
    html_block.append(_render_highlights_html(student_text, evidence))
    highlight_html = "".join(html_block)

    notes = {
        "ai_generated_likelihood": ai_like,
        "plagiarism_risk": plag_risk,
        "internal_candidates_used": [
            {"submission_id": str(s.id), "similarity_hint": sim} for s, sim in candidates
        ]
    }

    return {
        "best_submission": suspected,
        "best_score": plag_risk,
        "highlight_html": highlight_html,
        "notes": notes,
    }


@transaction.atomic
def build_or_update_report(new_submission: Submission) -> PlagiarismReport:
    """
    Luo tai päivittää PlagiarismReport-objektin annetulle opiskelijapalautukselle
    analysoimalla sen sisällön.

    Args:
        new_submission (Submission): Opiskelijan palautus, jolle raportti luodaan/päivitetään.

    Returns:
        PlagiarismReport: Luotu tai päivitetty plagiointiraportti.
    """
    result = analyze_plagiarism(new_submission)

    report, _ = PlagiarismReport.objects.select_for_update().get_or_create(
        submission=new_submission,
        defaults={
            "suspected_source": result["best_submission"],
            "score": result["best_score"],
            "highlights": result["highlight_html"],
        },
    )
    report.suspected_source = result["best_submission"]
    report.score = result["best_score"]
    report.highlights = result["highlight_html"]
    # Jos malliin on myöhemmin lisätty notes-kenttä, tallennetaan:
    if hasattr(report, "notes"):
        try:
            report.notes = result["notes"]
        except Exception: # Pyydystä tarkempi virhe, jos mahdollista
            pass
    report.created_at = report.created_at or timezone.now()
    report.save()
    return report