# materials/ai_service.py
from django.conf import settings
from openai import OpenAI
import os, base64

#Chunk toiminta kirjastot
from typing import List, Optional

SYSTEM_FIN = (
    #Muutin tätä, et sain ops käytön toimii t. Mirka
    "Olet tekoäly, joka laatii opetusmateriaaleja ja tehtäviä suoraan oppilaille suomeksi. Palauta TÄSMÄLLEEN tämä muoto:"
    "Kirjoita selkeällä suomen kielellä. Palauta TÄSMÄLLEEN tämä muoto:\n"
    "Otsikkoehdotus: <lyhyt otsikko>\n"
    "Tavoitteet:\n"
    "1) ...\n2) ...\n3) ...\n\n"
    "Luonnosteksti:\n- <Tähän varsinainen tehtävä tai tehtävät, jotka osoitetaan suoraan oppilaalle. Voit käyttää otsikointia, kuten 'Tehtävä 1:'.>"
)

def _demo(prompt: str) -> str:
    """
    Palauttaa demoversion tekoälyvastauksesta, kun API-avainta ei ole saatavilla.

    Args:
        prompt (str): Käyttäjän alkuperäinen syöte.

    Returns:
        str: Demovastaus, joka esittää tekoälyn formaattia.
    """
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
    """
    Kysyy Large Language Modelilta (LLM) vastausta annettuun promptiin.
    Käyttää OpenAI:n API:a. Jos API-avainta ei ole asetettu, palauttaa demovastauksen.
    Sisältää varautumismekanismin, jos LLM ei noudata annettua vastausformaattia.

    Args:
        prompt (str): Kysymys tai ohjeistus LLM:lle.
        user_id (int): Valinnainen käyttäjän ID, jota voidaan käyttää
                       API-kutsujen seurantaan tai personointiin.

    Returns:
        str: LLM:n generoitu vastaus tai demovastaus virheen sattuessa.
    """
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

def generate_image_bytes(prompt: str, size: str = "1024x1024") -> bytes:
    """
    Generoi kuvan DALL·E 3 -tekoälymallilla ja palauttaa sen PNG-muotoisena
    binaaridatana. Jos OpenAI API-avainta ei ole asetettu, palauttaa demokuvan.
    Käsittelee DALL·E 3:n mahdollisia vastausmuotoja (base64 tai URL).

    Args:
        prompt (str): Kuvaus siitä, millainen kuva halutaan generoida.
        size (str): Kuvan koko (esim. "256x256", "512x512", "1024x1024").
                    DALL·E 2 tukee vain näitä neliökokoja. Testikäytön jälkeen vaihto Dall·E 3:een.
                    Jätetään koodiin neliötuki, vaikka Dall·E 3 tukee muitakin kokoja.

    Returns:
        bytes: Generoitu kuva PNG-binaarimuodossa.

    Raises:
        ValueError: Jos annettu koko ei ole tuettu.
        RuntimeError: Jos kuvan generoinnissa tapahtuu virhe tai
                      API-vastaus on epäkelpo.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # DEMO-kuva
        from PIL import Image, ImageDraw, ImageFont
        import io
        img = Image.new("RGB", (1024, 1024), (28, 33, 40))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        d.multiline_text((40, 40), f"DEMO IMAGE\n{prompt[:120]}", font=font, fill=(230, 230, 230), spacing=6)
        buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()

    if size not in {"256x256", "512x512", "1024x1024"}:
        raise ValueError("DALL·E 2 tukee vain neliötä: 256/512/1024")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    try:
        resp = client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            size=size,
            n=1,
        )
        item = resp.data[0]

        # 1) Yritä base64
        b64 = getattr(item, "b64_json", None)
        if b64:
            return base64.b64decode(b64)

        # 2) Muutoin hae URL
        url = getattr(item, "url", None)
        if url:
            import requests
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.content

        # 3) Ei kumpaakaan → virhe
        raise RuntimeError("DALL·E 2 ei palauttanut b64_json- tai url-kenttää.")

    except Exception as e:
        raise RuntimeError(f"DALL·E 2 virhe: {e}") from e

#Puheen generointi OpenAI:n TTS:llä
def generate_speech(text_to_speak: str) -> bytes | None:
    """
    Muuntaa annetun tekstin puheeksi käyttäen OpenAI:n TTS-rajapintaa.
    Palauttaa äänidatan (MP3) bitteinä tai None, jos virhe tapahtuu
    tai API-avainta ei ole asetettu.

    Args:
        text_to_speak (str): Teksti, joka muunnetaan puheeksi.

    Returns:
        bytes | None: Äänidata MP3-muodossa tai None virheen sattuessa.
    """
    api_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        print("Text-to-Speech Error: OPENAI_API_KEY is not set.")
        return None

    try:
        client = OpenAI(api_key=api_key)
        
        response = client.audio.speech.create(
            model="tts-1",       # Voit kokeilla myös mallia "tts-1-hd"
            voice="fable",       # Voit kokeilla muita ääniä: 'echo', 'fable', 'onyx', 'nova', 'shimmer'
            input=text_to_speak,
            speed=0.95           # Säädä puheen nopeutta (0.25 - 4.0)
        )
        
        # Palautetaan raaka äänidata
        return response.content

    except Exception as e:
        print(f"An error occurred during TTS generation: {e}")
        return None
    
# --- OPS-konteksti LLM:lle ---
try:
    # Hakee chunkit JSONista
    from TaskuOpe.ops_chunks import retrieve_chunks, format_for_llm
    _HAS_OPS = True
except Exception:
    _HAS_OPS = False


def _build_prompt_with_context(question: str, context_block: str) -> str:
    """
    Rakentaa täydellisen promptin tekoälylle, yhdistäen käyttäjän kysymyksen
    ja opetussuunnitelman (OPS) kontekstin. Ohjeistaa tekoälyä käyttämään
    ainoastaan annettua OPS-kontekstia vastauksen perustana.

    Args:
        question (str): Käyttäjän alkuperäinen kysymys tai pyyntö.
        context_block (str): Opetussuunnitelman sisältö, joka tarjoaa kontekstin.

    Returns:
        str: Valmis prompt-teksti tekoälylle.
    """
    return (
        "Olet opettajan tekoälyavustaja. Tehtäväsi on luoda opetusmateriaalia alla olevan pyynnön ja opetussuunnitelman (OPS) otteiden pohjalta.\n\n"
        "Käytä AINOASTAAN annettua OPS-kontekstia materiaalisi perustana. Älä keksi tai lisää tietoa, jota kontekstissa ei ole.\n\n"
        "--- OPS-KONTEKSTI ---\n"
        f"{context_block}\n"
        "--- KONTEKSTI LOPPUU ---\n\n"
        f"Käyttäjän pyyntö: \"{question}\"\n\n"
        "Laadi opetusmateriaali pyydetyssä muodossa (Otsikkoehdotus, Tavoitteet, Luonnosteksti)."
    )

def ask_llm_with_ops(
    question: str,
    *,
    ops_query: str = "",
    subjects: Optional[List[str]] = None,
    grades: Optional[List[str]] = None,
    ctypes: Optional[List[str]] = None,
    k: int = 6,
    user_id: int = 0,
    max_chars: int = 8000
) -> dict:
    """
    Kysyy Large Language Modelilta (LLM) vastausta, johon on integroitu
    opetussuunnitelman (OPS) konteksti. Hakee OPS-chunkit annettujen kriteerien
    perusteella ja muotoilee ne promptiin.

    Args:
        question (str): Käyttäjän kysymys tekoälylle.
        ops_query (str): Valinnainen hakukysely OPS-chunkeille.
        subjects (Optional[List[str]]): Valinnainen lista oppiaineista.
        grades (Optional[List[str]]): Valinnainen lista luokka-asteista.
        ctypes (Optional[List[str]]): Valinnainen lista sisältötyypeistä.
        k (int): Kuinka monta OPS-chunkia haetaan.
        user_id (int): Valinnainen käyttäjän ID API-kutsuille.
        max_chars (int): Maksimimerkkimäärä promptille,
                         jonka jälkeen konteksti katkaistaan.

    Returns:
        dict: Sanakirja, joka sisältää LLM:n vastauksen ('answer')
              ja käytetyt OPS-chunkit ('used_chunks').
    """
    if not _HAS_OPS:
        return {"answer": ask_llm(question, user_id=user_id), "used_chunks": []}

    chunks = retrieve_chunks(
        query=ops_query or "",
        k=k,
        subjects=subjects or [],
        grades=grades or [],
        ctypes=ctypes or [],
    )
    context = format_for_llm(chunks)
    prompt = _build_prompt_with_context(question, context)

    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n\n[Katkaistu konteksti]"

    return {"answer": ask_llm(prompt, user_id=user_id), "used_chunks": chunks}

def ask_llm_with_given_chunks(
    question: str,
    chunks: List[dict],
    *,
    user_id: int = 0,
    max_chars: int = 8000
) -> dict:
    """
    Kysyy Large Language Modelilta (LLM) vastausta käyttäen ennalta annettuja
    opetussuunnitelman (OPS) chunkeja kontekstina. Tämä funktio on tarkoitettu
    tapauksiin, joissa chunkit on jo valittu ulkopuolisesti (esim. käyttöliittymästä).

    Args:
        question (str): Käyttäjän kysymys tekoälylle.
        chunks (List[dict]): Lista OPS-chunkeista, jotka annetaan kontekstina.
        user_id (int): Valinnainen käyttäjän ID API-kutsuille.
        max_chars (int): Maksimimerkkimäärä promptille,
                         jonka jälkeen konteksti katkaistaan.

    Returns:
        dict: Sanakirja, joka sisältää LLM:n vastauksen ('answer')
              ja käytetyt OPS-chunkit ('used_chunks').
    """
    if not chunks:
        return {"answer": ask_llm(question, user_id=user_id), "used_chunks": []}

    context = format_for_llm(chunks)
    prompt = _build_prompt_with_context(question, context)

    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n\n[Katkaistu konteksti]"

    return {"answer": ask_llm(prompt, user_id=user_id), "used_chunks": chunks}


