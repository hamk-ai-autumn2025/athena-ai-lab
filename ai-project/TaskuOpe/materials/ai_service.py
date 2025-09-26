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

def generate_image_bytes(prompt: str) -> bytes:
    """
    Palauttaa PNG-binaarit. Jos OPENAI_API_KEY puuttuu, luodaan demo-kuva Pillowilla.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # DEMO: generoidaan yksinkertainen PNG teksteineen
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            raise RuntimeError("Pillow ei ole asennettu (pip install Pillow).")
        img = Image.new("RGB", (1024, 576), color=(28, 33, 40))
        draw = ImageDraw.Draw(img)
        text = f"DEMO IMAGE\n{prompt[:80]}"
        # Fontti valinnaisesti järjestelmästä; käytä oletusta jos ei löydy
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        w, h = draw.multiline_textbbox((0, 0), text, font=font)[2:]
        draw.multiline_text(((1024 - w) // 2, (576 - h) // 2), text, fill=(230, 230, 230), font=font, align="center")
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # Oikea generointi OpenAI:lla (voit vaihtaa mallia esim. "gpt-image-1")
    client = OpenAI(api_key=api_key)
    resp = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x576",
        response_format="b64_json",
    )
    import base64
    b64 = resp.data[0].b64_json
    return base64.b64decode(b64)