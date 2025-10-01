# -*- coding: utf-8 -*-
# Kerää perusopetuksen (POPS 2014) 1–6 -luokkien tavoitteet, sisällöt ja arvioinnin
# ePerusteet-rajapinnasta. Korjaa kielten (oppimäärien) tyhjät tulokset käymällä
# rekursiivisesti läpi 'oppimaarat' ja poistamalla kapean VLK-koodisuodatuksen.

import requests
import json
import re
from typing import Any, Dict, List, Tuple

BASE_URL = "https://eperusteet.opintopolku.fi/eperusteet-service/api/external/peruste/419550/perusopetus"
SUBJECTS_URL = f"{BASE_URL}/oppiaineet"
HEADERS = {"Caller-Id": "script.opetussuunnitelma"}
TIMEOUT = 30

# Oppiaineet, jotka ohitetaan
SKIP_KEYWORDS = ["uskonto", "elämänkatsomustieto", "liikunta", "käsityö"]

OUTPUT_FILE = "opetussuunnitelma_1-6_API_data.json"


def get_text(value: Any, lang: str = "fi") -> str:
    """Palauttaa lokalisoidun tekstin, jos value on dict; muuten str(value)."""
    if value is None:
        return ""
    if isinstance(value, dict):
        if lang in value and value[lang]:
            return str(value[lang])
        for v in value.values():
            if v:
                return str(v)
        return ""
    return str(value)


def infer_grade_label(ctx: Dict[str, Any]) -> str:
    """
    Päättele kontekstin luokka-aste: '1-2', '3-6' tai fallback '1-6'.
    Ei kaadu, vaikka kenttien nimet vaihtelevat.
    """
    def pick_text(obj):
        return get_text(obj) if obj is not None else ""

    candidates: List[str] = []
    for key in ("vuosiluokkakokonaisuus", "vuosiluokkaKokonaisuus"):
        if key in ctx:
            v = ctx[key]
            if isinstance(v, dict):
                candidates += [
                    pick_text(v.get("nimi")),
                    pick_text(v.get("koodi")),
                    pick_text(v.get("koodiArvo")),
                    pick_text(v.get("koodiUri")),
                    pick_text(v.get("id")),
                ]
            else:
                candidates.append(pick_text(v))

    candidates += [
        pick_text(ctx.get("nimi")),
        pick_text(ctx.get("koodi")),
        pick_text(ctx.get("koodiArvo")),
        pick_text(ctx.get("koodiUri")),
        pick_text(ctx.get("id")),
    ]

    text = " ".join(candidates).lower()

    if re.search(r"(1\s*[-_–]\s*2)|(\b1\s*2\b)|(\b1–2\b)", text):
        return "1-2"
    if re.search(r"(3\s*[-_–]\s*6)|(\b3\s*6\b)|(\b3–6\b)", text):
        return "3-6"

    if ("1" in text and "2" in text) and not ("3" in text or "6" in text):
        return "1-2"
    if "3" in text and "6" in text:
        return "3-6"

    return "1-6"


def collect_from_context(ctx: Dict[str, Any], subject_label: str, results: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """
    EI suodata VLK-koodilla. Kerää tavoitteet, sisällöt ja arvioinnin kaikista löydetyistä kentistä.
    Leimaa rivit inferoidulla luokka-aste-merkinnällä.
    """
    grade_context_label = infer_grade_label(ctx)
    g_cnt = c_cnt = e_cnt = 0

    # --- Tavoitteet ---
    goals_list: List[Any] = []
    if ctx.get("tavoitteet"):
        goals_list = ctx["tavoitteet"]
    elif ctx.get("tavoitealueet"):
        for area in ctx["tavoitealueet"]:
            if isinstance(area, dict) and area.get("tavoitteet"):
                goals_list.extend(area["tavoitteet"])

    for goal in goals_list:
        if not isinstance(goal, dict):
            continue
        # Tavoitteen teksti voi olla useissa kentissä; katetaan yleisimmät
        text = (
            get_text(goal.get("tavoite"))
            or get_text(goal.get("nimi"))
            or get_text(goal.get("kuvaus"))
            or get_text(goal)
        )
        # Joissain rakenteissa tavoite -> {'teksti': {...}}
        if not text and isinstance(goal.get("tavoite"), dict):
            tdict = goal["tavoite"]
            text = get_text(tdict.get("teksti")) or get_text(tdict)

        if not text:
            continue

        results.append(
            {
                "source": "POPS_2014",
                "subject": subject_label,
                "grade_context": grade_context_label,
                "content_type": "Tavoite",
                "content": text,
            }
        )
        g_cnt += 1

    # --- Keskeiset sisällöt ---
    content_items: List[Any] = []
    for k in ("sisaltoalueet", "keskeisetSisallot", "sisallot"):
        if ctx.get(k):
            content_items = ctx[k]
            break

    for item in content_items:
        if not isinstance(item, dict):
            continue
        name_text = get_text(item.get("nimi"))
        desc_text = get_text(item.get("kuvaus"))
        content_text = f"{name_text}: {desc_text}" if name_text and desc_text else (desc_text or name_text)
        if not content_text:
            continue
        results.append(
            {
                "source": "POPS_2014",
                "subject": subject_label,
                "grade_context": grade_context_label,
                "content_type": "Keskeinen sisältö",
                "content": content_text,
            }
        )
        c_cnt += 1

    # --- Arviointi ---
    if ctx.get("arviointi") is not None:
        eval_value = ctx["arviointi"]
        if isinstance(eval_value, dict):
            eval_text = get_text(eval_value.get("teksti")) or get_text(eval_value.get("kuvaus")) or get_text(eval_value)
        else:
            eval_text = get_text(eval_value)
        if eval_text:
            results.append(
                {
                    "source": "POPS_2014",
                    "subject": subject_label,
                    "grade_context": grade_context_label,
                    "content_type": "Arviointi",
                    "content": eval_text,
                }
            )
            e_cnt += 1

    return g_cnt, c_cnt, e_cnt


def process_subject(detail_json: Dict[str, Any], base_name: str, results: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """
    Käsittelee sekä oppiaineen että sen oppimäärät (kielissä olennainen).
    Palauttaa (tavoitteet, sisällöt, arvioinnit).
    """
    total_g = total_c = total_e = 0

    # 1) Tason omat kontekstit (jos ei löydy, käsitellään olio itsessään kontekstina)
    contexts: List[Dict[str, Any]] = []
    if detail_json.get("vuosiluokkakokonaisuudet"):
        contexts = detail_json["vuosiluokkakokonaisuudet"]
    elif detail_json.get("vuosiluokkaKokonaisuudet"):
        contexts = detail_json["vuosiluokkaKokonaisuudet"]
    else:
        contexts = [detail_json]

    for ctx in contexts:
        if isinstance(ctx, dict):
            g, c, e = collect_from_context(ctx, base_name, results)
            total_g += g
            total_c += c
            total_e += e

    # 2) Oppimäärät (rekursio)
    if detail_json.get("oppimaarat"):
        for om in detail_json["oppimaarat"]:
            if not isinstance(om, dict):
                continue
            om_name = (get_text(om.get("nimi")) or get_text(om.get("kieli")) or get_text(om.get("taso"))).strip()
            level = (get_text(om.get("oppimaara")) or get_text(om.get("taso"))).strip()

            label_parts = [base_name]
            if om_name:
                label_parts.append(om_name)
            if level and (not om_name or level not in om_name):
                label_parts.append(level)
            child_label = " — ".join([p for p in label_parts if p])

            g, c, e = process_subject(om, child_label, results)
            total_g += g
            total_c += c
            total_e += e

    return total_g, total_c, total_e


def main():
    print("Haetaan oppiaineet...")
    try:
        resp = requests.get(SUBJECTS_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"Oppiaineiden hakeminen epäonnistui: {e}")
        return

    try:
        subjects = resp.json()
    except Exception as e:
        print(f"Oppiaineiden JSON-parsaus epäonnistui: {e}")
        return

    print(f"Löytyi {len(subjects)} oppiainetta.")

    results: List[Dict[str, Any]] = []

    for subj in subjects:
        if not isinstance(subj, dict):
            continue

        # Nimi
        name = ""
        if "nimi" in subj:
            name = get_text(subj["nimi"], lang="fi")
        elif "nimiFi" in subj:
            name = get_text(subj["nimiFi"], lang="fi")
        else:
            for key in ("name", "nimi"):
                if key in subj:
                    name = get_text(subj[key], lang="fi")
                    break

        if not name:
            continue

        # Ohita tietyt oppiaineet
        if any(kw in name.lower() for kw in SKIP_KEYWORDS):
            print(f"Ohitetaan oppiaine: {name}")
            continue

        # ID
        subj_id = subj.get("id") or subj.get("oppiaineId") or subj.get("tunniste")
        if not subj_id:
            continue

        print(f"Käsitellään oppiaine {name} (ID {subj_id})...")
        detail_url = f"{BASE_URL}/oppiaineet/{subj_id}"

        try:
            resp2 = requests.get(detail_url, headers=HEADERS, timeout=TIMEOUT)
            resp2.raise_for_status()
        except Exception as e:
            print(f"  Oppiaineen {name} tietojen haku epäonnistui: {e}")
            continue

        try:
            subj_detail = resp2.json()
        except Exception as e:
            print(f"  Oppiaineen {name} JSON-parsaus epäonnistui: {e}")
            continue

        g, c, e = process_subject(subj_detail, name, results)
        print(f"  -> Kerätty {g} tavoitetta, {c} sisältöä, {e} arviointia.")

    # Tallenna tulokset
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Valmis. Tulokset tallennettu tiedostoon {OUTPUT_FILE}.")


if __name__ == "__main__":
    main()
