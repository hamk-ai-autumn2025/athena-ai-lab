#!/usr/bin/env python3
"""
Product Description & Slogan Generator (images + optional user text)
- Lataa 1..N kuvaa
- Anna vapaaehtoinen tekstivihje (materiaalit, koko, kohderyhmä, tone)
- Generoi tuotetekstit + 3 lyhyttä slogania / kuva
- Ilman API-avainta: paikallinen heuristiikka
- Jos OPENAI_API_KEY on asetettu: pyydä LLM:ää hiomaan tekstiä (tekstiin perustuen, ei lähetä kuvaa API:lle)
"""
import os
from typing import List, Tuple
from PIL import Image
import gradio as gr

# Valinnainen OpenAI-vahvistus
USE_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
if USE_OPENAI:
    try:
        from openai import OpenAI
        oai_client = OpenAI()
    except Exception:
        USE_OPENAI = False

def simple_color_palette(img: Image.Image, k: int = 3) -> List[str]:
    im = img.convert("RGB").copy()
    im.thumbnail((64, 64))
    colors = im.getcolors(maxcolors=64 * 64)
    if not colors:
        return []
    colors = sorted(colors, key=lambda x: x[0], reverse=True)[:k]

    def rgb_to_name(rgb):
        r, g, b = rgb
        if r > 200 and g > 200 and b > 200: return "white"
        if r < 40 and g < 40 and b < 40: return "black"
        if r > 180 and g < 80 and b < 80: return "red"
        if r < 80 and g > 160 and b < 80: return "green"
        if r < 80 and g < 80 and b > 160: return "blue"
        if r > 180 and g > 180 and b < 80: return "yellow"
        if r > 200 and g < 120 and b > 200: return "magenta"
        if r < 120 and g > 200 and b > 200: return "cyan"
        if r > 180 and g > 120 and b < 80: return "orange"
        if r > 160 and g > 140 and b > 120: return "beige"
        return f"rgb({r},{g},{b})"

    return list(dict.fromkeys([rgb_to_name(c[1]) for c in colors]))

def rule_based_description(img: Image.Image, hint: str, filename: str) -> Tuple[str, List[str]]:
    w, h = img.size
    palette = simple_color_palette(img, k=4)
    name_guess = (
        filename.rsplit("/", 1)[-1].split(".")[0]
        .replace("_", " ").replace("-", " ").strip()
    )
    parts = []
    if name_guess:
        parts.append(f"Product: {name_guess.capitalize()}")
    if palette:
        parts.append("Key colors: " + ", ".join(palette))
    parts.append(f"Image resolution: {w}×{h}px")
    if hint:
        parts.append(f"User highlights: {hint.strip()}")

    core = " | ".join(parts)
    desc = (
        f"{core}. Crafted for everyday use with a focus on quality and clean design. "
        f"Materials and specs inferred from the image; verify exact details before publishing."
    )
    slogans = [
        f"{name_guess.title() if name_guess else 'This product'}, made simple.",
        f"Style meets function in {palette[0]}." if palette else "Style meets function.",
        "Ready for daily wins.",
    ]
    return desc, slogans

def openai_enhance(hint: str, filename: str, base_desc: str, base_slogans: List[str]) -> Tuple[str, List[str]]:
    """Tekstipohjainen hionta (ei lähetä kuvaa API:lle)"""
    if not USE_OPENAI:
        return base_desc, base_slogans
    try:
        prompt = f"""
You are an expert product copywriter. Improve the following product description and slogans.
Constraints:
- Be factual to what is stated; do not invent specs.
- Use the user's notes to increase accuracy.
- Keep 80–120 words for the description.
- Produce exactly 3 short slogans (max 7 words each).

Filename: {filename}
User notes: {hint or "N/A"}
Initial draft: {base_desc}
Initial slogans: {base_slogans}
Return:
1) Polished description paragraph.
2) Three slogans as a simple list.
"""
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You write concise, high-converting ecommerce copy and refuse to invent specs."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
        )
        text = resp.choices[0].message.content.strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        desc_lines, slog_lines, mode = [], [], "desc"
        for l in lines:
            if l.lower().startswith("slogan"):
                mode = "slog"
                continue
            if mode == "desc":
                desc_lines.append(l)
            else:
                slog_lines.append(l.lstrip("-•0123456789. ").strip())
        desc = " ".join(desc_lines) if desc_lines else base_desc
        slogs = [s for s in slog_lines if s][:3] or base_slogans
        return desc, slogs
    except Exception:
        return base_desc, base_slogans

def process(images: List[Image.Image], hints: str) -> List[List[str]]:
    results = []
    if not images:
        return [["No images uploaded.", "", "", "", ""]]
    for idx, img in enumerate(images):
        filename = getattr(img, "name", f"image_{idx+1}.png")
        base_desc, base_slogans = rule_based_description(img, hints, filename)
        desc, slogs = openai_enhance(hints, filename, base_desc, base_slogans)
        results.append([
            filename, desc,
            slogs[0],
            slogs[1] if len(slogs) > 1 else "",
            slogs[2] if len(slogs) > 2 else "",
        ])
    return results

# --- monikuvat File-komponentista + galleria-esikatselu ---
def process_files(file_objs, hints):
    """Lue useita kuvia File-komponentista, palauta (gallery_items, taulukko)."""
    images: List[Image.Image] = []
    gallery_items = []  # [(path, caption)]
    for f in (file_objs or []):
        p = getattr(f, "name", None)
        if not p and isinstance(f, dict):
            p = f.get("name") or f.get("path")
        if not p and isinstance(f, str):
            p = f
        if not p:
            continue
        try:
            img = Image.open(p).convert("RGB")
            img.name = os.path.basename(p)
            images.append(img)
            gallery_items.append((p, os.path.basename(p)))
        except Exception:
            pass
    table = process(images, hints)
    return gallery_items, table

with gr.Blocks(title="Product Description & Slogan Generator") as demo:
    gr.Markdown("# Product Description & Slogan Generator")
    with gr.Row():
        with gr.Column():
            files = gr.File(
                label="Upload product images",
                file_count="multiple",
                file_types=["image"]
            )
            hints = gr.Textbox(
                label="Optional: product details, target audience, tone, keywords",
                placeholder="e.g., 500ml insulated bottle, stainless steel, leak-proof, for commuters, tone: premium yet friendly",
            )
            run_btn = gr.Button("Generate")
        with gr.Column():
            gallery = gr.Gallery(
                label="Preview",
                show_label=True,
                columns=2,   # montako kuvaa rinnakkain
                height=400   # px
            )
            out = gr.Dataframe(
                headers=["file", "description", "slogan_1", "slogan_2", "slogan_3"],
                wrap=True
            )

    run_btn.click(fn=process_files, inputs=[files, hints], outputs=[gallery, out])
    gr.Markdown("**Note:** If OPENAI_API_KEY is set, the app will ask an LLM to refine the text. Otherwise, a local rule-based fallback is used.")

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",   # vain paikallinen
        server_port=int(os.getenv("PORT", "7860")),
        share=False
    )



