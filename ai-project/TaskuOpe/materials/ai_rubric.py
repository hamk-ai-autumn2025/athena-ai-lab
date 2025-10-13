# ai_rubric.py

import json
import re
from typing import Any, Dict, List

from django.utils import timezone

from .ai_service import ask_llm
from .models import AIGrade, Material, Rubric, RubricCriterion, Submission
from TaskuOpe.ops_chunks import format_for_llm, retrieve_chunks


# ---------- Apurit ----------

def _ensure_default_rubric(material: Material) -> Rubric:
    """
    Varmistaa, että materiaalille on olemassa rubriikki.
    Jos rubriikkia ei ole, luo uuden oletusrubriikin kolmella peruskriteerillä:
    Sisältö ja ymmärrys, Rakenne ja jäsentely, sekä Kieli ja oikeinkirjoitus.

    Args:
        material (Material): Materiaali, jolle rubriikki tarkistetaan/luodaan.

    Returns:
        Rubric: Materiaaliin liitetty rubriikki.
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
        ("Sisältö ja ymmärrys", 5, "Vastaus käsittelee tehtävän ydinsisältöä, on oikein ja täydellinen."),
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

# ======================================================================
# === LOPULLINEN, TARKENNETTU VERSIO PROMPTISTA ===
# ======================================================================
def _build_prompt(
    material: Material, submission: Submission, criteria: List[RubricCriterion]
) -> str:
    """
    Rakentaa tekoälylle tarkoitetun promptin, joka ohjeistaa sitä arvioimaan
    oppilaan vastauksen systemaattisesti ja analyyttisesti ennalta määriteltyjen
    kriteerien ja tehtävänannon perusteella. Prompti sisältää tehtävänannon otteen,
    oppilaan vastauksen, rubriikin kriteerit ja tarvittaessa opetussuunnitelman kontekstin.
    Tekoälyä ohjeistetaan palauttamaan JSON-muotoinen vastaus.

    Args:
        material (Material): Tehtävään liittyvä materiaali.
        submission (Submission): Oppilaan vastaus.
        criteria (List[RubricCriterion]): Lista rubriikin kriteereistä.

    Returns:
        str: Valmis prompt-teksti tekoälylle.
    """
    material_excerpt = (material.content or "").strip()[:2000] + "…"
    student_answer = (submission.response or "").strip()
    ops_context_str = ""

    try:
        subject, grade_level = material.subject, material.grade_level
        if subject and grade_level:
            ops_chunks = retrieve_chunks(query=material.title, subjects=[subject], grades=[grade_level], k=3)
            if ops_chunks:
                formatted_ops = format_for_llm(ops_chunks)
                ops_context_str = f"""
OPETUSSUUNNITELMAN RELEVANTIT TAVOITTEET/SISÄLLÖT TÄLLE TEHTÄVÄLLE:
\"\"\"
{formatted_ops}
\"\"\"
"""
    except Exception as e:
        print(f"DEBUG (ai_rubric): Could not retrieve OPS chunks: {e}")
        pass

    criterialines = [f'- "{c.name}" (max {c.max_points} p): {c.guidance or ""}'.strip() for c in criteria]

    prompt = f"""
Tehtäväsi on toimia systemaattisena ja analyyttisenä opettajan apulaisena. Arvioi oppilaan vastaus vertaamalla sitä HUOLELLISESTI ja kohta kohdalta tehtävänantoon ja rubriikin kriteereihin.

OHJEET ARVIOINTIIN:
1.  **VERTAA VASTAUSTA TEHTÄVÄNANTOON:** Käy läpi oppilaan vastaus ja vertaa sitä kohta kohdalta tehtävänantoon. Tunnista, mitkä tehtävät on tehty, mitkä ovat virheellisiä ja mitkä puuttuvat kokonaan.
2.  **PISTEYTÄ SISÄLTÖ KATTAVUUDEN MUKAAN:** "Sisältö ja ymmärrys" -kriteeri arvioi suoraan vastausten kattavuutta ja oikeellisuutta. Tämä on tärkein vaihe. Käytä nyrkkisääntöä: jos puolet tehtävistä puuttuu, tämän kriteerin pisteet eivät voi olla yli puolet maksimista. Jos kaikkiin on vastattu mutta niissä on virheitä, vähennä pisteitä virheiden vakavuuden mukaan.
3.  **ARVIOI MUUT KRITEERIT:** Arvioi "Rakenne" ja "Kieli" erikseen vastauksen kirjoitetun osuuden perusteella.
4.  **ANNA RAKENTAVA PALAUTE:** Kirjoita palaute, joka on kannustava, mutta rehellinen. Mainitse selkeästi puuttuvat tehtävät ja virheet.

MATERIAALIN OTSIKKO: {material.title}
TEHTÄVÄNANTO (ote):
\"\"\"{material_excerpt}\"\"\"

{ops_context_str}

OPPILAAN VASTAUS:
\"\"\"{student_answer}\"\"\"

RUBRIIKKI (kriteerit):
{chr(10).join(criterialines)}

Palauta vastaus TÄSMÄLLISESTI JSON-muodossa ilman muuta tekstiä:
{{
  "criteria": [
    {{"name": "<kriteerin nimi>", "points": <int>, "max": <int>, "feedback": "<Kannustava, mutta rehellinen ja tarkka palaute>"}}
  ],
  "general_feedback": "<Ystävällinen yhteenveto, joka mainitsee sekä onnistumiset että tärkeimmät kehityskohteet.>"
}}
"""
    return prompt.strip()


def _extract_json_block(text: str) -> Dict[str, Any]:
    """
    Poimii JSON-muotoisen lohkon annetusta tekstistä.
    Etsii joko koodilohkon (` ```json ... ``` `) tai pelkän JSON-objektin (` { ... } `).
    Yrittää ladata JSON:in ja käsittelee mahdolliset virheet.
    Käsittelee myös tapauksia, joissa JSON sisältää kommentteja.

    Args:
        text (str): Teksti, josta JSON-lohko yritetään poimia.

    Returns:
        Dict[str, Any]: Parsittu JSON-objekti sanakirjana, tai tyhjä sanakirja, jos parsinta epäonnistuu.
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


def create_or_update_ai_grade(submission: Submission) -> AIGrade:
    """
    Luo tai päivittää tekoälyn antaman arvosanan (AIGrade) annetulle vastaukselle (Submission).
    Funktio:
    1. Varmistaa, että submissionin materiaalille on olemassa oletusrubriikki.
    2. Rakentaa promptin tekoälylle rubriikin ja submissionin perusteella.
    3. Kutsuu tekoälypalvelua (`ask_llm`) ja poimii vastauksesta JSON-muotoisen arvioinnin.
    4. Käsittelee tekoälyn antamat kriteerikohtaiset pisteet ja palautteen.
    5. Tallentaa tai päivittää AIGrade-objektin tietokantaan.

    Args:
        submission (Submission): Oppilaan vastaus, joka arvioidaan.

    Returns:
        AIGrade: Luotu tai päivitetty tekoälyarvosana.
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
                matched = by_name.get(name.lower()) or next((c for c in criteria if c.name.lower() not in {i["name"].lower() for i in criteria_out}), None)
                if not matched: continue
                max_p = int(matched.max_points)
                points = max(0, min(points, max_p))
                total += points
                max_total += max_p
                criteria_out.append({"name": matched.name, "points": points, "max": max_p, "feedback": str(item.get("feedback", "")).strip()})
            except Exception:
                continue
    if not criteria_out:
        for c in criteria:
            max_total += int(c.max_points)
            criteria_out.append({"name": c.name, "points": 0, "max": int(c.max_points), "feedback": ""})
    general_feedback = str(data.get("general_feedback", "")).strip() if isinstance(data, dict) else ""
    details = {"criteria": criteria_out, "general_feedback": general_feedback, "rubric_title": rubric.title, "generated_at": timezone.now().isoformat()}
    ag, _created = AIGrade.objects.get_or_create(submission=submission)
    ag.rubric = rubric
    ag.total_points = float(round(total, 2))
    ag.details = details
    ag.teacher_confirmed = False
    ag.save()
    return ag