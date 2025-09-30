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
    # --- MUUTOS ALKAA TÄSTÄ ---
    # Haetaan tehtävän luokkataso materiaalin tiedoista turvallisesti.
    grade_level_prompt_line = ""
    try:
        # Polku on submission -> assignment -> material -> grade_level
        grade_level = submission.assignment.material.grade_level
        if grade_level:
            # Muotoillaan selkeä ohje tekoälylle.
            grade_level_prompt_line = f"HUOMIOITAVA LUOKKATASO: Tämä tehtävä on suunniteltu {grade_level}. luokan oppilaalle. Arvioi vastaus tämän ikätason vaatimusten mukaisesti.\n"
    except Exception:
        # Jos tietoa ei jostain syystä löydy, jatketaan ilman sitä.
        pass
    # --- MUUTOS PÄÄTTYY TÄHÄN ---

    criterialines = []
    for c in criteria:
        criterialines.append(f'- "{c.name}" (max {c.max_points} p): {c.guidance or ""}'.strip())

    material_excerpt = (material.content or "").strip()
    if len(material_excerpt) > 2500:
        material_excerpt = material_excerpt[:2500] + " …"

    student_answer = (submission.response or "").strip()

    prompt = f"""
Tehtävä: Arvioi oppilaan vastaus rubriikin perusteella ja anna pisteet kullekin kriteerille.
Pisteytys vain kokonaislukuna välillä 0..max kriteerikohtaisesti. Anna lisäksi lyhyt palaute.

{grade_level_prompt_line} # <-- TÄSSÄ LISÄTTY TIETO LUOKKATASOSTA
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
    fence = re.search(r"```(?:json)?\s*({.*?})\s*```", text, flags=re.S)
    raw = fence.group(1) if fence else None
    if not raw:
        m = re.search(r"(\{.*\})", text, flags=re.S)
        raw = m.group(1) if m else None
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        cleaned = re.sub(r"//.*", "", raw)
        try:
            return json.loads(cleaned)
        except Exception:
            return {}


# ---------- Julkinen API ----------

def create_or_update_ai_grade(submission: Submission) -> AIGrade:
    """
    Luo tai päivittää AI:n arviointiehdotuksen (AIGrade) tälle palautukselle.
    """
    material = submission.assignment.material
    rubric = _ensure_default_rubric(material)
    criteria = list(rubric.criteria.order_by("order", "id"))
    prompt = _build_prompt(material, submission, criteria)
    llm_text = ask_llm(prompt, user_id=getattr(submission.assignment.assigned_by, "id", 0))
    data = _extract_json_block(llm_text)

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
                matched = by_name.get(name.lower())
                if matched is None:
                    matched = next((c for c in criteria if c.name.lower() not in {i["name"].lower() for i in criteria_out}), None)
                    if matched is None:
                        continue
                max_p = int(matched.max_points)
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

    ag, _created = AIGrade.objects.get_or_create(submission=submission)
    ag.rubric = rubric
    ag.total_points = float(round(total, 2))
    ag.details = details
    ag.teacher_confirmed = False
    ag.save()

    return ag