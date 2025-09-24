# pip install Unidecode
import os
import sys
import io
import time
import warnings
import numpy as np
import sounddevice as sd
import wavio
import soundfile as sf
from openai import OpenAI
from unidecode import unidecode

# Poistetaan turhat varoitukset
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Äänityksen asetukset
FS = 44100
CHANNELS = 1
DTYPE = 'int16'
SAMPWIDTH = 2
OUT_DIR = os.path.join(os.path.dirname(__file__), "recordings")
OUT_WAV = os.path.join(OUT_DIR, "speech.wav")

client = OpenAI()

translation_lang = "English"

# ---- Latin-tunnistus + translitterointi ----
_LATIN_RANGES = [
    (0x0041, 0x024F),  # Basic Latin + Latin-1 Supplement + Latin Extended-A/B
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2C60, 0x2C7F),  # Latin Extended-C
    (0xA720, 0xA7FF),  # Latin Extended-D
]

def _is_latin_char(ch: str) -> bool:
    cp = ord(ch)
    if not ch.isalpha():  # salli numerot, välimerkit, emojit
        return True
    return any(a <= cp <= b for (a, b) in _LATIN_RANGES)

def contains_non_latin(s: str) -> bool:
    return any(ch.isalpha() and not _is_latin_char(ch) for ch in s)

def transliterate(text: str) -> str:
    return unidecode(text or "").strip()

# ---- Audio I/O ----
def record_until_enter(fs=FS, channels=CHANNELS, dtype=DTYPE):
    """Aloita äänitys Enterillä, lopeta seuraavalla Enterillä."""
    input("Press enter, wait 2 seconds and start speaking... You can speak any language.")
    print("Recording... Press Enter to stop.")

    frames = []

    def callback(indata, frames_count, time_info, status):
        if status:
            print(f"[SD status] {status}", file=sys.stderr)
        frames.append(indata.copy())

    stream = sd.InputStream(samplerate=fs, channels=channels, dtype=dtype, callback=callback)
    stream.start()
    try:
        input()
    finally:
        stream.stop()
        stream.close()

    if not frames:
        return np.zeros((0, channels), dtype=dtype)
    return np.concatenate(frames, axis=0)

def save_wav(path, audio, fs=FS, sampwidth=SAMPWIDTH):
    """Tallentaa WAV-tiedoston recordings/-kansioon."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wavio.write(path, audio, fs, sampwidth=sampwidth)

# ---- OpenAI ----
def transcribe_with_openai(wav_path, model="gpt-4o-mini-transcribe"):
    """STT muunnos WAV-tiedostosta tekstiksi. Palauttaa pelkän tekstin."""
    with open(wav_path, "rb") as f:
        resp = client.audio.transcriptions.create(model=model, file=f)
    return (resp.text or "").strip()

def translate_with_openai(text, target_lang=translation_lang, model="gpt-4o-mini"):
    """Käännös halutulle kielelle käyttäjän syötteen mukaan."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": f"You are a translator. Translate everything into {target_lang}. Do not answer anything else. Just translate the text."},
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content

def tts_stream_play(text, model="gpt-4o-mini-tts", voice="alloy", fmt="wav"):
    """Tekstistä puhetta ja soitetaan suoraan muistista."""
    spoken_response = client.audio.speech.create(
        model=model,
        voice=voice,
        response_format=fmt,  # "wav", "mp3", "opus", "flac", ...
        input=text,
    )

    # Talletetaan puskuriin
    buffer = io.BytesIO()
    for chunk in spoken_response.iter_bytes(chunk_size=4096):
        buffer.write(chunk)
    buffer.seek(0)

    # Soitetaan suoraan
    with sf.SoundFile(buffer, "r") as sound_file:
        data = sound_file.read(dtype="int16")
        sd.play(data, sound_file.samplerate)
        sd.wait()

# ---- Main ----
def main():
    while True:
        # Äänitys
        audio = record_until_enter()
        if audio.size == 0:
            print("Data missing. Try again.")
            continue

        # Tallennetaan wav tiedostoon puhe
        save_wav(OUT_WAV, audio)

        t0 = time.time()

        # STT
        try:
            text = transcribe_with_openai(OUT_WAV)
            print("\n=== Speech to text ===")
            if contains_non_latin(text):
                translit = transliterate(text)
                # Näytetään alkuperäinen + latinalaisin kirjaimin
                print(text)
                print(f"[{translit}]")
            else:
                print(text)

            t1 = time.time()
            print(f"(Transcription took {t1 - t0:.2f} s)")

            # Kysytään käyttäjältä käännöskieli + käännös (käännetään AINA alkuperäinen teksti)
            target = input("\nGive translation language (e.g. English, Finnish, Swedish): ").strip() or "English"
            translation = translate_with_openai(text, target_lang=target)
            print(f"\n=== Translation ({target}) ===")
            print(translation)
            t2 = time.time()
            print(f"(Translation took {t2 - t1:.2f} s)")

            # TTS suoraan bufferista
            tts_stream_play(translation, fmt="wav")
            t3 = time.time()
            print(f"(TTS took {t3 - t2:.2f} s)")

            time.sleep(0.8)  # Lyhyt paussi, muuten katkaisee puheen kesken

            # Jatketaanko
            again = input("\nSo you want another translation? (Enter = Yes, q = Quit): ")
            if again.strip().lower() == "q":
                print("Quiting.")
                break

        except Exception as e:
            print(f"Transcription/translation/TTS failed: {e}")

if __name__ == "__main__":
    main()
