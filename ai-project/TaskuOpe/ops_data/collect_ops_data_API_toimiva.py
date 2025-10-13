'''
"""
Kerää perusopetuksen (POPS 2014) 1–6 -luokkien datan ePerusteet-rajapinnasta.

Käsittelee vain ennalta määritellyt, halutut oppiaineet.
'''

import requests
import json
import re
from typing import Any, Dict, List, Tuple

BASE_URL = "https://eperusteet.opintopolku.fi/eperusteet-service/api/external/peruste/419550/perusopetus"
SUBJECTS_URL = f"{BASE_URL}/oppiaineet"
HEADERS = {"Caller-Id": "script.opetussuunnitelma"}
TIMEOUT = 30
OUTPUT_FILE = "opetussuunnitelma_1-6_API_data.json"

# ======================================================================
# === SÄILYTETTÄVIEN OPPIAINEIDEN LISTA ("WHITELIST")               ====
# ======================================================================
# Vain nämä oppiaineet (ja niiden alaosat, kuten kielet) otetaan mukaan.
# Nimet on pienennetty ja yksinkertaistettu vastaamaan API-dataa.
KEEP_SUBJECTS = [
    "fysiikka",
    "historia",
    "kemia",
    "kotitalous",
    "kuvataide",
    "maantieto",
    "biologia",
    "ympäristöoppi",
    "matematiikka",
    "musiikki",
    "terveystieto", # Kattaa myös 'terveysoppi'-maininnat
    "yhteiskuntaoppi",
    "äidinkieli ja kirjallisuus" # Kattaa kaikki äidinkielen oppimäärät
]

def get_text(value: Any, lang: str = "fi") -> str:
    """
    Hakee tekstiarvon syötetystä datasta ensisijaisesti määritetyllä kielellä.

    Args:
        value (Any): Diktionääri, merkkijono tai muu arvo, josta teksti haetaan.
        lang (str): Haluttu kielikoodi (esim. "fi", "sv"). Oletus: "fi".

    Returns:
        str: Tekstiarvo. Palauttaa tyhjän merkkijonon, jos arvoa ei löydy.
    """
    if value is None: return ""
    if isinstance(value, dict):
        if lang in value and value[lang]: return str(value[lang])
        for v in value.values():
            if v: return str(v)
        return ""
    return str(value)

def _find_all_strings_recursively(data: Any) -> List[str]:
    """
    Etsii kaikki merkkijonot rekursiivisesti annetusta datarakenteesta.

    Args:
        data (Any): Diktionääri, lista tai merkkijono, josta merkkijonoja etsitään.

    Returns:
        List[str]: Lista löytyneistä merkkijonoista.
    """
    strings = []
    if isinstance(data, dict):
        for value in data.values(): strings.extend(_find_all_strings_recursively(value))
    elif isinstance(data, list):
        for item in data: strings.extend(_find_all_strings_recursively(item))
    elif isinstance(data, str): strings.append(data)
    return strings

def infer_grade_label(ctx: Dict[str, Any]) -> str:
    """
    Päättelee vuosiluokka-alueen (esim. "1-2" tai "3-6") tekstikontekstista.

    Args:
        ctx (Dict[str, Any]): Kontekstidiktionääri, josta etsitään vuosiluokkatietoa.

    Returns:
        str: Päätelty vuosiluokka-alue merkkijonona tai tyhjä merkkijono, jos ei löydy.
    """
    all_texts = _find_all_strings_recursively(ctx)
    text = " ".join(all_texts).lower()
    if re.search(r"(vuosiluokilla\s*3-6)|(3\s*[-_–]\s*6)|(\b3\s*6\b)|(\b3–6\b)", text): return "3-6"
    if re.search(r"(vuosiluokilla\s*1-2)|(1\s*[-_–]\s*2)|(\b1\s*2\b)|(\b1–2\b)", text): return "1-2"
    return ""

def collect_from_context(
    ctx: Dict[str, Any],
    subject_label: str,
    grade_context_label: str,
    results: List[Dict[str, Any]],
) -> Tuple[int, int, int]:
    """
    Kerää tavoitteet, sisällöt ja arvioinnit annetusta kontekstista.

    Args:
        ctx (Dict[str, Any]): Kontekstidiktionääri (esim. oppiaineen tai vuosiluokan tiedot).
        subject_label (str): Käsiteltävän oppiaineen nimi.
        grade_context_label (str): Päätelty vuosiluokka-alue.
        results (List[Dict[str, Any]]): Lista, johon kerätyt tiedot lisätään.

    Returns:
        Tuple[int, int, int]: Kerättyjen tavoitteiden, sisältöjen ja arviointien määrät.
    """

    g_cnt = c_cnt = e_cnt = 0
    goals_list: List[Any] = []

    if ctx.get("tavoitteet"): goals_list = ctx["tavoitteet"]
    elif ctx.get("tavoitealueet"):
        for area in ctx["tavoitealueet"]:
            if isinstance(area, dict) and area.get("tavoitteet"): goals_list.extend(area["tavoitteet"])

    for goal in goals_list:
        if not isinstance(goal, dict): continue
        text = get_text(goal.get("tavoite")) or get_text(goal.get("nimi")) or get_text(goal.get("kuvaus"))
        if not text and isinstance(goal.get("tavoite"), dict): text = get_text(goal["tavoite"].get("teksti"))
        if not text: continue
        results.append({"source": "POPS_2014", "subject": subject_label, "grade_context": grade_context_label, "content_type": "Tavoite", "content": text})
        g_cnt += 1

    content_items: List[Any] = []

    for k in ("sisaltoalueet", "keskeisetSisallot", "sisallot"):
        if ctx.get(k): content_items = ctx[k]; break

    for item in content_items:
        if not isinstance(item, dict): continue
        name_text = get_text(item.get("nimi")); desc_text = get_text(item.get("kuvaus"))
        content_text = f"{name_text}: {desc_text}" if name_text and desc_text else (desc_text or name_text)
        if not content_text: continue
        results.append({"source": "POPS_2014", "subject": subject_label, "grade_context": grade_context_label, "content_type": "Keskeinen sisältö", "content": content_text})
        c_cnt += 1

    if ctx.get("arviointi") is not None:
        eval_value = ctx["arviointi"]
        eval_text = get_text(eval_value.get("teksti")) if isinstance(eval_value, dict) else get_text(eval_value)
        if eval_text:
            results.append({"source": "POPS_2014", "subject": subject_label, "grade_context": grade_context_label, "content_type": "Arviointi", "content": eval_text})
            e_cnt += 1
            
    return g_cnt, c_cnt, e_cnt

def process_subject(
    detail_json: Dict[str, Any],
    base_name: str,
    results: List[Dict[str, Any]],
    inherited_grade_label: str = "",
) -> Tuple[int, int, int]:
    """
    Käsittelee oppiaineen tai sen alaosan tiedot rekursiivisesti.

    Args:
        detail_json (Dict[str, Any]): Oppiaineen tai sen osan yksityiskohtaiset tiedot.
        base_name (str): Oppiaineen perusnimi.
        results (List[Dict[str, Any]]): Lista, johon kerätyt tiedot lisätään.
        inherited_grade_label (str): Peritty vuosiluokka-alue ylemmästä kontekstista.

    Returns:
        Tuple[int, int, int]: Kerättyjen tavoitteiden, sisältöjen ja arviointien kokonaismäärät.
    """

    total_g = total_c = total_e = 0
    current_grade_label = infer_grade_label(detail_json) or inherited_grade_label

    g, c, e = collect_from_context(detail_json, base_name, current_grade_label, results)
    total_g += g; total_c += c; total_e += e

    contexts: List[Dict[str, Any]] = []

    if detail_json.get("vuosiluokkakokonaisuudet"): contexts = detail_json["vuosiluokkakokonaisuudet"]
    elif detail_json.get("vuosiluokkaKokonaisuudet"): contexts = detail_json["vuosiluokkaKokonaisuudet"]

    for ctx in contexts:
        if isinstance(ctx, dict):
            g, c, e = process_subject(ctx, base_name, results, inherited_grade_label=current_grade_label)
            total_g += g; total_c += c; total_e += e

    if detail_json.get("oppimaarat"):
        for om in detail_json["oppimaarat"]:
            if not isinstance(om, dict): continue
            om_name = (get_text(om.get("nimi")) or get_text(om.get("kieli"))).strip()
            child_label = f"{base_name} — {om_name}" if om_name else base_name
            g, c, e = process_subject(om, child_label, results, inherited_grade_label=current_grade_label)
            total_g += g; total_c += c; total_e += e

    return total_g, total_c, total_e

def main():
    """
    Pääohjelma, joka hakee, käsittelee ja tallentaa perusopetuksen aineistoja.
    """
    print("Haetaan oppiaineet...")
    try:
        resp = requests.get(SUBJECTS_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status(); subjects = resp.json()
    except Exception as e:
        print(f"Oppiaineiden haku epäonnistui: {e}"); return

    print(f"Löytyi {len(subjects)} oppiainetta.")
    results: List[Dict[str, Any]] = []
    kept_subjects_count = 0

    for subj in subjects:
        if not isinstance(subj, dict): continue
        name = get_text(subj.get("nimi")) or get_text(subj.get("nimiFi"))
        
        # Jos oppiaineen nimi ei sisällä mitään avainsanaa KEEP_SUBJECTS-listalta, ohita se.
        if not any(keep_name in name.lower() for keep_name in KEEP_SUBJECTS):
            continue
        
        kept_subjects_count += 1
        subj_id = subj.get("id") or subj.get("oppiaineId")
        if not subj_id: continue

        print(f"Käsitellään oppiaine {name} (ID {subj_id})...")
        try:
            resp2 = requests.get(f"{BASE_URL}/oppiaineet/{subj_id}", headers=HEADERS, timeout=TIMEOUT)
            resp2.raise_for_status(); subj_detail = resp2.json()
        except Exception as e:
            print(f"  Oppiaineen {name} tietojen haku epäonnistui: {e}"); continue
        
        g, c, e = process_subject(subj_detail, name, results)
        print(f"  -> Kerätty {g} tavoitetta, {c} sisältöä, {e} arviointia.")

    print(f"\nKäsiteltiin {kept_subjects_count} oppiainetta KEEP_SUBJECTS-listan perusteella.")
    
    final_results = [res for res in results if res.get("grade_context")]
    print(f"Kerättiin yhteensä {len(results)} tietuetta.")
    print(f"Suodatettiin pois {len(results) - len(final_results)} tietuetta ilman selkeää luokka-astetta.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    print(f"Valmis. {len(final_results)} tietuetta tallennettu tiedostoon {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()