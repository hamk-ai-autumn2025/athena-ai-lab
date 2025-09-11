# materials/ai_service.py
import os
from openai import OpenAI

SYSTEM_FIN = (
    "Kirjoita opetusmateriaalia suomeksi. Palauta TÄSMÄLLEEN tämä muoto:\n"
    "Otsikkoehdotus: <lyhyt otsikko>\n"
    "Tavoitteet:\n"
    "1) ...\n2) ...\n3) ...\n\n"
    "Luonnosteksti:\n- <varsinainen sisältö, luettelona tai kappaleina>"
)

def _demo(prompt: str) -> str:
    p = (prompt or '').strip()[:300]
    return (
        "[DEMO] AI ei vielä käytössä (ei API-avainta).\n\n"
        "Otsikkoehdotus: Luonnos aiheen perusteella\n"
        "Tavoitteet:\n"
        "1) Ymmärtää peruskäsitteet\n"
        "2) Harjoitella keskeisiä taitoja\n"
        "3) Soveltaa opittua käytäntöön\n\n"
        f"Luonnosteksti:\n- {p or 'Kirjoita pyyntö ylle ja lähetä.'}\n"
    )

def ask_llm(prompt: str, *, user_id: int = 0) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _demo(prompt)

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(  # virallinen Chat Completions -kutsu
            model="gpt-4o-mini",               # voit vaihtaa esim. "gpt-4o"
            messages=[
                {"role": "system", "content": SYSTEM_FIN},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        out = (resp.choices[0].message.content or "").strip()
        # Varmistus: jos malli ei seurannut formaattia, tee kevyt fallback
        if "Otsikkoehdotus:" not in out or "Luonnosteksti:" not in out:
            out = (
                "Otsikkoehdotus: Luonnos\n"
                "Tavoitteet:\n1) ...\n2) ...\n3) ...\n\n"
                f"Luonnosteksti:\n- {out}"
            )
        return out
    except Exception as e:
        # Älä kaada näkymää; palauta demomuoto virheilmoituksella
        return _demo(f"{prompt}\n\n[HUOM: API-virhe: {e}]")
