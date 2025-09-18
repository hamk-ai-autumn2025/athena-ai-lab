from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- Utilities ----------

def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^a-zA-Z0-9-_]+", "-", text.strip().lower())
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "img"


def aspect_to_openai_size(aspect: str) -> str:
    """
    OpenAI (gpt-image-1) tukee: 1024x1024, 1536x1024 (vaaka), 1024x1536 (pysty), tai 'auto'.
    Mäpätään yleiset suhteet niihin.
    """
    a = aspect.strip().lower()
    if a == "auto":
        return "auto"
    if a in {"1:1", "square"}:
        return "1024x1024"
    if a in {"16:9", "3:2"}:
        return "1536x1024"  # vaaka
    if a in {"9:16", "2:3"}:
        return "1024x1536"  # pysty
    if a in {"4:3"}:
        return "1536x1024"
    if a in {"3:4"}:
        return "1024x1536"

    m = re.match(r"^(\d+):(\d+)$", a)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w == h:
            return "1024x1024"
        return "1536x1024" if w > h else "1024x1536"

    raise SystemExit(f"Unsupported aspect ratio: {aspect}")


def save_png(data: bytes, out_prefix: str, idx: int) -> Path:
    fname = Path(f"{slugify(out_prefix)}-{now_stamp()}-oai-{idx}.png")
    fname.write_bytes(data)
    return fname


# ---------- OpenAI generation ----------

def generate_openai(
    prompt: str,
    n: int,
    aspect: str,
    out_prefix: str,
    *,
    model: str = "gpt-image-1",
    quality: Optional[str] = None,       # esim. low|medium|high|auto (jos tuettu)
    style: Optional[str] = None,         # valinnainen; API voi ohittaa
    background: Optional[str] = None,    # esim. 'transparent'
    base_url: Optional[str] = None,
    timeout: int = 60,
    negative: Optional[str] = None,      # ei tuettu OpenAI-kuvissa -> ohitetaan
    seed: Optional[int] = None,          # ei tuettu OpenAI-kuvissa -> ohitetaan
) -> Tuple[List[Path], List[str]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: OPENAI_API_KEY puuttuu ympäristömuuttujista.")

    size = aspect_to_openai_size(aspect)
    base = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    url = base + "/images/generations"

    payload = {
        "model": model,
        "prompt": prompt,
        "n": max(1, int(n)),
        "size": size,
    }
    if quality:
        payload["quality"] = quality
    if style:
        payload["style"] = style
    if background:
        payload["background"] = background

    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = session.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    if resp.status_code >= 400:
        raise SystemExit(f"OpenAI API error {resp.status_code}: {resp.text}")

    data = resp.json()
    items = data.get("data") or []
    if not items:
        raise SystemExit("OpenAI ei palauttanut kuvia.")

    saved_paths: List[Path] = []
    download_urls: List[str] = []
    for i, item in enumerate(items, 1):
        if item.get("url"):
            download_urls.append(item["url"])
            img = session.get(item["url"], timeout=timeout).content
            saved_paths.append(save_png(img, out_prefix, i))
        elif item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
            p = save_png(raw, out_prefix, i)
            download_urls.append(p.resolve().as_uri())
            saved_paths.append(p)
        else:
            raise SystemExit("Rivissä ei ollut url tai b64_json -kenttää.")
    return saved_paths, download_urls


# ---------- Gyazo upload ----------

def upload_to_gyazo(
    image_path: Path,
    access_token: str,
    *,
    title: Optional[str] = None,
    desc: Optional[str] = None,
    referer_url: Optional[str] = None,
    timeout: int = 60,
) -> dict:
    """
    Lataa kuvan Gyazoon.
    Vaatii access tokenin (asetettava ympäristömuuttujaan GYAZO_ACCESS_TOKEN).
    Palauttaa Gyazon JSON-vastauksen.
    """
    url = "https://upload.gyazo.com/api/upload"
    with image_path.open("rb") as f:
        files = {"imagedata": f}
        data = {"access_token": access_token}
        if title:
            data["title"] = title
        if desc:
            data["desc"] = desc
        if referer_url:
            data["referer_url"] = referer_url
        r = requests.post(url, files=files, data=data, timeout=timeout)
        r.raise_for_status()
        return r.json()


# ---------- CLI ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="imgcli",
        description=(
            "Komentorivityökalu OpenAI-kuvien generointiin (gpt-image-1). "
            "Tulostaa URLit ja tallentaa tiedostot. (Valinnainen Gyazo-upload)"
        ),
    )
    p.add_argument("-p", "--prompt", required=True, help="Kuvaus (prompt).")
    p.add_argument("-n", "--num", type=int, default=1, help="Kuvien lukumäärä (oletus: 1).")
    p.add_argument("-a", "--aspect", default="1:1", help="1:1, 16:9, 9:16, 4:3, 3:4, W:H, tai 'auto'.")
    p.add_argument("-o", "--output", default=None, help="Tiedostonimen etuliite (slug tehdään automaattisesti).")

    # Specin mukaiset liput (hyväksytään, vaikka OpenAI ei käytä näitä):
    p.add_argument("-x", "--negative", default=None, help="[ignored] Negative prompt if supported.")
    p.add_argument("-s", "--seed", type=int, default=None, help="[ignored] Seed if supported.")

    # OpenAI-valinnat
    p.add_argument("--oai-model", default="gpt-image-1", help="OpenAI-kuvamalli.")
    p.add_argument("--oai-quality", default=None, help="Esim. low|medium|high|auto (jos tuettu).")
    p.add_argument("--oai-style", default=None, help="Valinnainen tyyli.")
    p.add_argument("--oai-background", default=None, help="Esim. 'transparent'.")
    p.add_argument("--oai-base-url", default=None, help="Mukautettu API-pohja, jos tarvitset.")
    p.add_argument("--timeout", type=int, default=300, help="Sekunteja HTTP-pyyntöjen aikakatkaisuun.")

    # Gyazo-valinnat
    p.add_argument("--gyazo", action="store_true", help="Lähetä generoidut kuvat Gyazoon.")
    p.add_argument("--gyazo-title", default=None, help="Kuvan otsikko (valinnainen).")
    p.add_argument("--gyazo-desc", default=None, help="Kuvauksen teksti (valinnainen).")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    out_prefix = args.output or slugify(args.prompt)

    saved, urls = generate_openai(
        prompt=args.prompt,
        n=args.num,
        aspect=args.aspect,
        out_prefix=out_prefix,
        model=args.oai_model,
        quality=args.oai_quality,
        style=args.oai_style,
        background=args.oai_background,
        base_url=args.oai_base_url,
        timeout=args.timeout,
        negative=args.negative,
        seed=args.seed,
    )

    print("Backend: OpenAI")
    print("Download URLs:")
    for u in urls:
        print("  ", u)
    print("Saved files:")
    for pth in saved:
        print("  ", pth.name)

    # ---- Gyazo upload (valinnainen) ----
    if getattr(args, "gyazo", False):
        gyazo_token = os.getenv("GYAZO_ACCESS_TOKEN")
        if not gyazo_token:
            raise SystemExit("ERROR: GYAZO_ACCESS_TOKEN puuttuu (asetettava ympäristömuuttujaan).")

        gyazo_title = getattr(args, "gyazo_title", None) or args.prompt
        gyazo_desc = getattr(args, "gyazo_desc", None)
        gyazo_referer = getattr(args, "gyazo_referer", None)

        print("Gyazo uploads:")
        for pth in saved:
            try:
                res = upload_to_gyazo(
                    pth,
                    gyazo_token,
                    title=gyazo_title,
                    desc=gyazo_desc,
                    referer_url=gyazo_referer,
                    timeout=args.timeout,
                )
                permalink = res.get("permalink_url") or res.get("url")
                image_id = res.get("image_id")
                thumb = res.get("thumb_url")
                print(f"  {pth.name} -> {permalink}  (id={image_id}, thumb={thumb})")
            except Exception as e:
                print(f"  {pth.name} -> Gyazo upload FAILED: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
