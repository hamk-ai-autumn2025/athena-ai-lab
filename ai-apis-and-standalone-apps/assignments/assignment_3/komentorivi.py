#!/usr/bin/env python3
# llm_writer.py
import os, sys, argparse, textwrap, re
from typing import List
from openai import OpenAI

# ---------- Asetukset ----------
DEFAULT_MODEL = os.getenv("LLM_WRITER_MODEL", "gpt-4o")  # vaihda tarvittaessa

FORMATS = {
    "marketing": "kirjoitat vakuuttavaa markkinointimateriaalia (mainos, somepostaus, landing-teksti).",
    "meme": "keksit ja muotoilet meemejä, punchlineja ja napakoita kuvatekstejä.",
    "song": "kirjoitat iskeviä, riimillisiä laulunsanoituksia (säv. jaoittelu: [Verse]/[Pre-Chorus]/[Chorus]/[Bridge]).",
    "poem": "kirjoitat runoja (vaihtele mittaa, rytmiä ja kielikuvia).",
    "blog": "kirjoitat SEO-optimoituja blogitekstejä (otsikko, ingressi, väliotsikot, yhteenveto, CTA).",
}

VARIANT_SETTINGS = [
    # 3 eri makua / parametria (voit muokata)
    dict(name="Luova",  temperature=1.10, top_p=0.85, presence_penalty=0.90, frequency_penalty=0.50),
    dict(name="Lyrinen",temperature=0.95, top_p=0.90, presence_penalty=0.70, frequency_penalty=0.60),
    dict(name="Terävä", temperature=0.75, top_p=0.95, presence_penalty=0.50, frequency_penalty=0.30),
]

# ---------- Promptit ----------
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
    if fmt == "meme":
        extras.append("Tuota 3–5 mememuotoista ideaa (teksti + kuvateksti).")
    if fmt == "song":
        extras.append("Sisällytä toistettava kertosäe ja koukku.")
    if fmt == "poem":
        extras.append("Kokeile vaihtelevaa rytmiä ja kuvastoa.")
    if fmt == "blog":
        extras.append("Käytä H2/H3-väliotsikoita ja CTA-lopetus.")
    if keywords:
        extras.append(f"Käytä luonnollisesti avainsanoja ja synonyymejä: {', '.join(keywords)}.")
    if length:
        extras.append(f"Toivottu pituus/tiiviys: {length}.")
    extras.append("Kirjoita ilman täytesanoja. Tee jokaisesta versiosta selvästi erilainen.")
    return f"Pyyntö: {task}\n" + "\n".join(extras)

# ---------- Post-prosessointi ----------
BLOCK_REGEX = re.compile(r"<BEGIN_BLOCK>(.*)</END_BLOCK>", flags=re.DOTALL | re.IGNORECASE)

def extract_single_block(text: str) -> str:
    """
    Palauttaa vain yhden, ensimmäisen blokin.
    Jos rajamerkkejä ei löydy, yrittää leikata ensimmäisen 'SEO-otsikko:'-osion.
    """
    m = BLOCK_REGEX.search(text)
    if m:
        return m.group(1).strip()

    # Fallback, jos malli ei totellut rajoja
    low = text.lower()
    start = low.find("seo-otsikko:")
    if start == -1:
        return text.strip()
    # Leikkaa ennen seuraavaa 'seo-otsikko:' tai uutta '=== versio'
    next1 = low.find("\nseo-otsikko:", start + 1)
    next2 = low.find("=== versio", start + 1)
    cut_positions = [p for p in (next1, next2) if p != -1]
    cut = min(cut_positions) if cut_positions else len(text)
    return text[start:cut].strip()

# ---------- Generointi ----------
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
        text = extract_single_block(raw)  # pakota yksilohko
        if not text.startswith("=== Versio"):
            text = f"=== Versio #{i+1} ({s['name']}) ===\n" + text
        outputs.append(text)
    return outputs

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Luova LLM-kirjoittaja (oletuksena 3 versiota, yksi lohko per versio).")
    parser.add_argument("prompt", help="Aihe/pyyntö luonnollisella kielellä.")
    parser.add_argument("--format", choices=list(FORMATS.keys()), default="marketing", help="Tuotemuoto.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI-malli (oletus: gpt-4o).")
    parser.add_argument("--lang", default="fi", help="Kieli (fi, en, ...).")
    parser.add_argument("--audience", default="", help="Kohdeyleisö (esim. B2B-päättäjät, nuoret aikuiset).")
    parser.add_argument("--tone", default="", help="Äänensävy (esim. lämmin, napakka, humoristinen).")
    parser.add_argument("--keywords", default="", help="Pilkuin eroteltu lista avainsanoista.")
    parser.add_argument("--length", default="", help="Toivottu pituus (esim. 120–200 sanaa tai 'hyvin tiivis').")
    parser.add_argument("--out", default="", help="Tallenna tiedostoon (md).")
    parser.add_argument("--variants", type=int, default=3, help="Kuinka monta versiota (oletus 3).")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Virhe: Aseta ympäristömuuttuja OPENAI_API_KEY.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()  # lukee avaimen ympäristöstä

    system_prompt = build_system_prompt(args.format, args.audience, args.tone, args.lang)
    keywords_list = [s.strip() for s in args.keywords.split(",") if s.strip()]
    user_prompt = build_user_prompt(args.prompt, args.format, keywords_list, args.length)

    variants = generate_variants(client, args.model, system_prompt, user_prompt, n_variants=args.variants)

    joined = "\n\n".join(variants)
    print(joined)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("# Generoidut versiot\n\n")
            f.write(joined + "\n")
        print(f"\nTallennettu: {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()

