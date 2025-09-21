#!/usr/bin/env python3
# komentorivi.py – interaktiivinen LLM-kirjoittaja (oletus 3 versiota)

import os, sys, argparse, textwrap, re
from typing import List
from openai import OpenAI

DEFAULT_MODEL = os.getenv("LLM_WRITER_MODEL", "gpt-4o")

FORMATS = {
    "marketing": "kirjoitat vakuuttavaa markkinointimateriaalia (mainos, somepostaus, landing-teksti).",
    "meme": "keksit ja muotoilet meemejä, punchlineja ja napakoita kuvatekstejä.",
    "song": "kirjoitat iskeviä, riimillisiä laulunsanoituksia (säv. jaoittelu: [Verse]/[Pre-Chorus]/[Chorus]/[Bridge]).",
    "poem": "kirjoitat runoja (vaihtele mittaa, rytmiä ja kielikuvia).",
    "blog": "kirjoitat SEO-optimoituja blogitekstejä (otsikko, ingressi, väliotsikot, yhteenveto, CTA).",
}

VARIANT_SETTINGS = [
    dict(name="Luova",  temperature=1.10, top_p=0.85, presence_penalty=0.90, frequency_penalty=0.50),
    dict(name="Lyrinen",temperature=0.95, top_p=0.90, presence_penalty=0.70, frequency_penalty=0.60),
    dict(name="Terävä", temperature=0.75, top_p=0.95, presence_penalty=0.50, frequency_penalty=0.30),
]

BLOCK_REGEX = re.compile(r"<BEGIN_BLOCK>(.*)</END_BLOCK>", flags=re.DOTALL | re.IGNORECASE)

def build_system_prompt(fmt: str, audience: str, tone: str, lang: str) -> str:
    role = FORMATS.get(fmt, FORMATS["marketing"])
    return textwrap.dedent(f"""
    Olet palkittu luova kirjoittaja ja SEO-strategi. Kirjoitat kielellä: {lang}.
    Rooli: {role}
    Tyyli: {tone or "luonteva, selkeä, vivahteikas"}.
    Kohdeyleisö: {audience or "yleisö"}.

    Ohje formaattiin (TÄRKEÄ):
    - TUOTA TÄSMÄLLEEN YKSI LOHKO per vastaus.
    - Kirjoita sisältö vain seuraavien rajojen väliin:
      <BEGIN_BLOCK>
      === Versio {{n}} ===
      SEO-otsikko:
      Meta-kuvaus:
      Avainsanat:
      Sisältö:
      </END_BLOCK>
    - Älä kirjoita mitään rajojen ulkopuolelle.
    - SEO: synonyymit ja semanttiset lähikäsitteet luonnollisesti, ei avainsanaspämmiä.
    - Vältä toistoa (verbit, adjektiivit, rakenteet). Ei täytesanoja.
    """).strip()

def build_user_prompt(task: str, fmt: str, keywords: List[str], length: str) -> str:
    extras = []
    if fmt == "meme": extras.append("Tuota 3–5 mememuotoista ideaa (teksti + kuvateksti).")
    if fmt == "song": extras.append("Sisällytä toistettava kertosäe ja koukku.")
    if fmt == "poem": extras.append("Kokeile vaihtelevaa rytmiä ja kuvastoa.")
    if fmt == "blog": extras.append("Käytä H2/H3-väliotsikoita ja CTA-lopetus.")
    if keywords: extras.append(f"Käytä luonnollisesti avainsanoja ja synonyymejä: {', '.join(keywords)}.")
    if length: extras.append(f"Toivottu pituus/tiiviys: {length}.")
    extras.append("Kirjoita ilman täytesanoja. Tee jokaisesta versiosta selvästi erilainen.")
    return f"Pyyntö: {task}\n" + "\n".join(extras)

def extract_single_block(text: str) -> str:
    m = BLOCK_REGEX.search(text)
    if m: return m.group(1).strip()
    low = text.lower()
    start = low.find("seo-otsikko:")
    if start == -1: return text.strip()
    next1 = low.find("\nseo-otsikko:", start + 1)
    next2 = low.find("=== versio", start + 1)
    cut_positions = [p for p in (next1, next2) if p != -1]
    cut = min(cut_positions) if cut_positions else len(text)
    return text[start:cut].strip()

def generate_variants(client: OpenAI, model: str, system_prompt: str, user_prompt: str, n_variants: int = 3) -> List[str]:
    outputs = []
    for i in range(n_variants):
        s = VARIANT_SETTINGS[i % len(VARIANT_SETTINGS)].copy()
        flavor = f"\nTyylimauste: {s['name']}.\n"
        messages = [
            {"role": "system", "content": system_prompt.replace("{n}", str(i+1)) + flavor},
            {"role": "user",   "content": user_prompt},
        ]
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=s["temperature"],
            top_p=s["top_p"],
            presence_penalty=s["presence_penalty"],
            frequency_penalty=s["frequency_penalty"],
            max_tokens=900,
        )
        raw = resp.choices[0].message.content.strip()
        text = extract_single_block(raw)
        if not text.startswith("=== Versio"):
            text = f"=== Versio #{i+1} ({s['name']}) ===\n" + text
        outputs.append(text)
    return outputs

def run_once_interactive(client: OpenAI, model: str):
    print("LLM-kirjoittaja (interaktiivinen). Paina Enter hyväksyäksesi oletukset.")
    prompt = input("Prompti (pakollinen): ").strip()
    if not prompt:
        print("Ei promptia. Keskeytetään.")
        return
    fmt = input("Muoto [marketing/meme/song/poem/blog] (oletus marketing): ").strip().lower() or "marketing"
    if fmt not in FORMATS: 
        print("Tuntematon muoto, käytetään 'marketing'."); fmt = "marketing"
    lang = input("Kieli (oletus fi): ").strip() or "fi"
    audience = input("Kohdeyleisö (valinn.): ").strip()
    tone = input("Äänensävy (valinn.): ").strip()
    keywords = input("Avainsanat pilkuin (valinn.): ").strip()
    length = input("Toivottu pituus (valinn., esim. 200–300 sanaa): ").strip()
    variants_str = input("Versioiden määrä (oletus 3): ").strip()
    variants = int(variants_str) if variants_str.isdigit() and int(variants_str) > 0 else 3
    out = input("Tallenna tiedostoon (esim. tulos.md) [Enter=ei tallennusta]: ").strip()

    system_prompt = build_system_prompt(fmt, audience, tone, lang)
    keywords_list = [s.strip() for s in keywords.split(",") if s.strip()]
    user_prompt = build_user_prompt(prompt, fmt, keywords_list, length)

    results = generate_variants(client, model, system_prompt, user_prompt, n_variants=variants)
    joined = "\n\n".join(results)
    print("\n" + joined + "\n")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("# Generoidut versiot\n\n")
            f.write(joined + "\n")
        print(f"Tallennettu: {out}")

def main():
    parser = argparse.ArgumentParser(
        description="Luova LLM-kirjoittaja. Ilman argumentteja käynnistyy interaktiivinen tila."
    )
    parser.add_argument("prompt", nargs="?", help="Aihe/pyyntö. Jos puuttuu, ohjelma kysyy sen.")
    parser.add_argument("--format", choices=list(FORMATS.keys()), help="Tuotemuoto.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI-malli (oletus: gpt-4o).")
    parser.add_argument("--lang", help="Kieli (oletus fi).")
    parser.add_argument("--audience", help="Kohdeyleisö.")
    parser.add_argument("--tone", help="Äänensävy.")
    parser.add_argument("--keywords", help="Pilkuin erotellut avainsanat.")
    parser.add_argument("--length", help="Toivottu pituus.")
    parser.add_argument("--out", help="Tallenna tiedostoon (md).")
    parser.add_argument("--variants", type=int, help="Versioiden määrä (oletus 3).")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Virhe: Aseta ympäristömuuttuja OPENAI_API_KEY.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()

    # Interaktiivinen tila, jos promptia ei annettu:
    if not args.prompt:
        return run_once_interactive(client, args.model)

    # Ei-interaktiivinen: käytä CLI-argumentteja
    fmt = (args.format or "marketing")
    lang = (args.lang or "fi")
    audience = (args.audience or "")
    tone = (args.tone or "")
    keywords_list = [s.strip() for s in (args.keywords or "").split(",") if s.strip()]
    length = (args.length or "")
    variants = args.variants if (args.variants and args.variants > 0) else 3

    system_prompt = build_system_prompt(fmt, audience, tone, lang)
    user_prompt = build_user_prompt(args.prompt, fmt, keywords_list, length)
    variants_txt = generate_variants(client, args.model, system_prompt, user_prompt, n_variants=variants)

    joined = "\n\n".join(variants_txt)
    print(joined)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("# Generoidut versiot\n\n")
            f.write(joined + "\n")
        print(f"\nTallennettu: {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
