import os, json, re, tempfile, warnings
import gradio as gr
import numpy as np
import soundfile as sf
import librosa

from faster_whisper import WhisperModel
from openai import OpenAI

# =========================
# Asetukset (ympäristömuuttujat)
# =========================
def _auto_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") not in (None, "", "-1") else "cpu"

def _auto_compute(dev):
    # GPU: float16, CPU: int8
    return "float16" if dev == "cuda" else "int8"

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3")   # tiny/base/small/medium/large-v3
_user_device = os.getenv("WHISPER_DEVICE", "auto")
_user_compute = os.getenv("WHISPER_COMPUTE")

WHISPER_DEVICE = _auto_device() if _user_device == "auto" else _user_device
WHISPER_COMPUTE = _user_compute or _auto_compute(WHISPER_DEVICE)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Suomisanasto vihjeeksi Whisperille
INITIAL_HINT = (
    "Konteksti: suomalainen kotiruoka, reseptit, raaka-aineet ja yksiköt: tl, rkl, dl, uuni, "
    "paistinpannu, sipuli, valkosipuli, kana, jauheliha, peruna, porkkana, kerma, maito, voi, "
    "suola, pippuri. Kuuntele vain suomea."
)

# =========================
# STT-mallin alustus (turvallinen fallback)
# =========================
def _init_whisper(model_size, device, compute):
    # Yritä ensisijaiset asetukset → järkevät fallbackit
    prefs = [(device, compute)]
    if device == "cuda":
        prefs += [("cuda", "float16"), ("cpu", "int8"), ("cpu", "float32")]
    else:
        prefs += [("cpu", "int8"), ("cpu", "float32")]
    last = None
    for dev, comp in prefs:
        try:
            return WhisperModel(model_size, device=dev, compute_type=comp)
        except Exception as e:
            last = e
    raise last

stt_model = _init_whisper(WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE)

# =========================
# STT
# =========================
def transcribe_audio(audio_tuple):
    """
    gr.Audio(..., type='numpy') -> (sr, np.ndarray)
    Palauttaa: teksti (str)
    """
    if audio_tuple is None:
        return ""
    sr, data = audio_tuple

    # Mono & float32
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    data = data.astype(np.float32)

    # Kevyt normalisointi
    peak = np.max(np.abs(data)) or 1.0
    data = data / peak

    # Resamplaa 16k
    if sr != 16000:
        data = librosa.resample(y=data, orig_sr=sr, target_sr=16000)
        sr = 16000

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        sf.write(tmp.name, data, sr)
        segments, info = stt_model.transcribe(
            tmp.name,
            language="fi",
            task="transcribe",
            initial_prompt=INITIAL_HINT,
            beam_size=8,
            patience=0.1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 200},
            condition_on_previous_text=False,
            temperature=0.0,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

# =========================
# LLM (OpenAI)
# =========================
client = OpenAI(api_key=OPENAI_API_KEY if OPENAI_API_KEY else None)

SYSTEM_PROMPT = """Puhu VAIN suomea. Olet suomalainen keittiöapuri.
Palauta TÄYDELLINEN JSON (ei muuta tekstiä) avaimilla:
- title: string
- ingredients: string[]
- steps: string[]
- notes: string
Max 10 vaihetta, arkinen kotiruoka.
"""

# JSON-parsinta varmistuksella
_num_prefix_re = re.compile(r"^\s*\d+\s*[\.\)\-:]\s*")
def _strip_num_prefix(s: str) -> str:
    return _num_prefix_re.sub("", s.strip())

def _fallback_response(msg: str):
    return (
        f"### Reseptivaiheet\n{msg}",
        "### Ainesosat\n- (ei saatavilla)"
    )

def generate_recipe(ingredients_text: str):
    if not ingredients_text or not ingredients_text.strip():
        return None

    if not OPENAI_API_KEY:
        return _fallback_response("LLM-avainta ei ole asetettu (OPENAI_API_KEY).")

    user_prompt = (
        f"Raaka-aineet: {ingredients_text}\n"
        f"Muista: Palaa vain JSONilla, ilman selitystekstiä."
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"}  # pakota validi JSON
        )
        content = resp.choices[0].message.content
        data = json.loads(content)

        title = (data.get("title", "Resepti") or "Resepti").strip()
        ingredients = [i.strip() for i in data.get("ingredients", []) if isinstance(i, str) and i.strip()]
        steps_raw = [s for s in data.get("steps", []) if isinstance(s, str) and s.strip()]
        steps = [_strip_num_prefix(s) for s in steps_raw]  # poista tuplanumerointi
        notes = (data.get("notes", "") or "").strip()

        steps_md = f"### {title}\n\n#### Reseptivaiheet\n" + "\n".join([f"1. {s}" for s in steps]) if steps else f"### {title}\n\n(Ei vaiheita)"
        ing_md = "### Ainesosat\n" + ("\n".join([f"- {x}" for x in ingredients]) if ingredients else "- (ei aineksia)")
        if notes:
            ing_md += f"\n\n**Vinkit:** {notes}"

        return steps_md, ing_md

    except Exception as e:
        return _fallback_response(f"LLM-pyyntö epäonnistui: {e}")

# =========================
# Gradio UI
# =========================
with gr.Blocks(title="Kokkauskaveri") as demo:
    gr.Markdown("# 🧑‍🍳 Kokkauskaveri")
    gr.Markdown("Puhu mikrofoniin raaka-aineet (esim. *kana, riisi, paprika, valkosipuli*) **tai** syötä ne tekstinä. Paina **Luo resepti**.")

    with gr.Row():
        audio = gr.Audio(sources=["microphone"], type="numpy", label="🎤 Nauhoita raaka-aineet")
    with gr.Row():
        ing_text = gr.Textbox(label="✍️ Syötä raaka-aineet käsin (vaihtoehto)", placeholder="esim. peruna, sipuli, voi, maito")
    with gr.Row():
        transcribed = gr.Textbox(label="Tunnistettu teksti (STT)", interactive=False, placeholder="Tähän ilmestyy puheesta tunnistettu teksti.")
    with gr.Row():
        make_btn = gr.Button("Luo resepti", variant="primary")

    with gr.Row():
        steps_out = gr.Markdown(label="Reseptivaiheet")
        ingred_out = gr.Markdown(label="Ainesosat")

    def do_make(audio_tuple, manual_text):
        # 1) Jos on ääni → transkriboi. 2) Muuten käytä manuaalista. 3) Jos molemmat, etusija äänellä.
        txt = transcribe_audio(audio_tuple) if audio_tuple is not None else (manual_text or "")
        res = generate_recipe(txt) if txt else None
        # transcribed-kenttään näytetään käytetty teksti (joko STT tai manuaali)
        return (txt, *(res if res else ("### Reseptivaiheet\n(ei sisältöä)", "### Ainesosat\n- (ei sisältöä)")))

    make_btn.click(do_make, inputs=[audio, ing_text], outputs=[transcribed, steps_out, ingred_out])

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    demo.queue().launch()







