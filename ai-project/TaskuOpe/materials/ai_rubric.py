import json
import re
from typing import List, Dict, Any

from django.utils import timezone

from .models import Rubric, RubricCriterion, AIGrade, Material, Submission
from .ai_service import ask_llm


# ---------- Apurit ----------

def _ensure_default_rubric(material: Material) -> Rubric:
    """
    Luo materiaalille yksinkertaisen oletusrubriikin, jos sellaista ei ole.
    Kolme peruskriteeriä (5 p / kriteeri): Sisältö, Rakenne, Kieli.
    """
    rubric = material.rubrics.first()
    if rubric:
        return rubric

    rubric = Rubric.objects.create(
        material=material,
        title=f"Rubriikki: {material.title[:60]}",
        created_by=material.author,
    )
    defaults = [
        ("Sisältö ja ymmärrys", 5, "Vastaus käsittelee tehtävän ydinsisältöä ja osoittaa ymmärrystä."),
        ("Rakenne ja jäsentely", 5, "Looginen rakenne, kappalejako ja punainen lanka."),
        ("Kieli ja oikeinkirjoitus", 5, "Sanasto, lauserakenne ja oikeinkirjoitus."),
    ]
    for idx, (name, maxp, guide) in enumerate(defaults):
        RubricCriterion.objects.create(
            rubric=rubric,
            name=name,
            max_points=maxp,
            guidance=guide,
            order=idx,
        )
    return rubric


def _build_prompt(material: Material, submission: Submission, criteria: List[RubricCriterion]) -> str:
    criterialines = []
    for c in criteria:
        criterialines.append(f'- "{c.name}" (max {c.max_points} p): {c.guidance or ""}'.strip())

    material_excerpt = (material.content or "").strip()
    # Pidä prompt siistinä: tarpeen mukaan lyhennä pitkää materiaalia
    if len(material_excerpt) > 2500:
        material_excerpt = material_excerpt[:2500] + " …"

    student_answer = (submission.response or "").strip()

    prompt = f"""
Tehtävä: Arvioi oppilaan vastaus rubriikin perusteella ja anna pisteet kullekin kriteerille.
Pisteytys vain kokonaislukuna välillä 0..max kriteerikohtaisesti. Anna lisäksi lyhyt palaute.

MATERIAALIN OTSIKKO: {material.title}
TEHTÄVÄN KUVAUS (ote):
\"\"\"{material_excerpt}\"\"\"

OPPILAAN VASTAUS:
\"\"\"{student_answer}\"\"\"

RUBRIIKKI (kriteerit):
{chr(10).join(criterialines)}

Palauta vastaus TÄSMÄLLE JSON-muodossa ilman muuta tekstiä:

{{
  "criteria": [
    {{"name": "<kriteerin nimi>", "points": <int>, "max": <int>, "feedback": "<yksi–kaksi virkettä>"}}
    // ... jokaisesta kriteeristä oma objekti
  ],
  "general_feedback": "<2–4 virkkeen yhteispalaute>"
}}

Huomioi: käytä vain sallittua rakennetta ja pidä pisteet kokonaislukuina.
"""
    return prompt.strip()


def _extract_json_block(text: str) -> Dict[str, Any]:
    """
    Yrittää löytää ja jäsentää ensimmäisen JSON-lohkon vastauksesta.
    Palauttaa dictin tai {}.
    """
    # Etsi koodiaidan sisällä oleva JSON tai suora JSON-objekti
    fence = re.search(r"```(?:json)?\s*({.*?})\s*```", text, flags=re.S)
    raw = fence.group(1) if fence else None
    if not raw:
        # fallback: ensimmäinen aaltosulkeilla alkava objekti
        m = re.search(r"(\{.*\})", text, flags=re.S)
        raw = m.group(1) if m else None
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        # Kevyt siivous: poista mahdollisia trailing-kommentteja
        cleaned = re.sub(r"//.*", "", raw)
        try:
            return json.loads(cleaned)
        except Exception:
            return {}


# ---------- Julkinen API ----------

def create_or_update_ai_grade(submission: Submission) -> AIGrade:
    """
    Luo tai päivittää AI:n arviointiehdotuksen (AIGrade) tälle palautukselle.
    Ei välitä mallin nimestä ai_service:lle (se määräytyy ai_service.py:ssä).
    """
    material = submission.assignment.material

    # Varmista rubriikki (automaattinen oletus, jos puuttuu)
    rubric = _ensure_default_rubric(material)
    criteria = list(rubric.criteria.order_by("order", "id"))

    # Rakenna prompt ja kysy LLM:ltä
    prompt = _build_prompt(material, submission, criteria)
    # HUOM: ei malliparametria — ai_service päättää mallin
    llm_text = ask_llm(prompt, user_id=getattr(submission.assignment.assigned_by, "id", 0))

    data = _extract_json_block(llm_text)

    # Jäsennä pisteet turvallisesti
    criteria_out = []
    total = 0.0
    max_total = 0
    by_name = {c.name.lower(): c for c in criteria}

    items = data.get("criteria") if isinstance(data, dict) else None
    if isinstance(items, list):
        for item in items:
            try:
                name = str(item.get("name", "")).strip()
                points = int(item.get("points", 0))
                # sovita oikeaan kriteeriin nimen perusteella (case-insensitive)
                matched = by_name.get(name.lower())
                if matched is None:
                    # jos nimeä ei tunnisteta, mapataan ensimmäiseen käyttämättömään
                    matched = next((c for c in criteria if c.name.lower() not in {i["name"].lower() for i in criteria_out}), None)
                    if matched is None:
                        continue

                max_p = int(matched.max_points)
                # rajoita 0..max
                points = max(0, min(points, max_p))

                total += points
                max_total += max_p

                criteria_out.append({
                    "name": matched.name,
                    "points": points,
                    "max": max_p,
                    "feedback": str(item.get("feedback", "")).strip(),
                })
            except Exception:
                continue

    # Jos LLM ei tuottanut kelvollista listaa, tee tyhjä ehdotus rakenteella
    if not criteria_out:
        for c in criteria:
            max_total += int(c.max_points)
            criteria_out.append({
                "name": c.name,
                "points": 0,
                "max": int(c.max_points),
                "feedback": "",
            })
        total = 0.0

    general_feedback = ""
    if isinstance(data, dict):
        gf = data.get("general_feedback")
        if isinstance(gf, str):
            general_feedback = gf.strip()

    details = {
        "criteria": criteria_out,
        "general_feedback": general_feedback,
        "rubric_title": rubric.title,
        "generated_at": timezone.now().isoformat(),
    }

    # Tallenna AIGrade
    ag, _created = AIGrade.objects.get_or_create(submission=submission)
    ag.rubric = rubric
    # Mallin nimi määritellään ai_service.py:ssä; jätetään mahdolliseen oletukseen/models defaultiin
    # Halutessasi voit pitää aiemmin tallennetun nimen ennallaan.
    ag.total_points = float(round(total, 2))
    ag.details = details
    ag.teacher_confirmed = False  # uusi ehdotus ei ole vielä vahvistettu
    ag.save()

    return ag
