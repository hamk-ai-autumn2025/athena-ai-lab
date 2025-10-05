# app.py — Single-file web image generator (Demo + OpenAI)
# Run:   python app.py
# Real images: export OPENAI_API_KEY="sk-proj-xxxx"

from flask import Flask, request, jsonify, make_response, Response
from openai import OpenAI
import urllib.request
import os

app = Flask(__name__)

# OpenAI client (None if missing -> use Demo mode in UI)
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

HTML = '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>AI Image Generator</title>
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;margin:0;background:#0b1020;color:#e6e9ef}
      .wrap{max-width:1000px;margin:0 auto;padding:24px}
      .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
      @media(max-width:900px){.grid{grid-template-columns:1fr}}
      .card{background:#111730;border:1px solid #1c2547;border-radius:14px;padding:16px}
      label{display:block;font-size:12px;color:#aab3d0;margin-bottom:6px}
      input,select,textarea,button{width:100%;box-sizing:border-box;border-radius:10px;border:1px solid #2a3564;background:#0e1430;color:#e6e9ef;padding:10px}
      textarea{min-height:84px;resize:vertical}
      button{cursor:pointer;background:#33409a;border-color:#3a49ad}
      .gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
      .thumb{position:relative;border-radius:12px;overflow:hidden;border:1px solid #263160;background:#0e1430;padding-bottom:10px}
      .thumb img{width:100%;height:260px;object-fit:cover;display:block}
      .error{color:#ff8b8b;background:#3a0f16;border:1px solid #6b1e29;padding:8px;border-radius:8px}

        .actions{
          display:flex;
          justify-content:center;
          gap:8px;
          margin-top:8px;
        }
        .actions button{
          width:auto;              /* override the global 100% */
          padding:6px 10px;
          font-size:12px;
          border-radius:8px;
        }
        .thumb{ padding-bottom:8px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Image Generator</h1>
      <div class="grid">
        <!-- Left controls -->
        <div class="card">
          <label for="prompt">Prompt</label>
          <textarea id="prompt" placeholder="Describe the image you want…"></textarea>

          <label for="neg" style="margin-top:12px">Negative prompt (optional)</label>
          <input id="neg" placeholder="What to avoid (e.g., blur, low quality)" />

          <div style="display:flex;gap:10px;margin-top:12px">
            <div style="flex:1">
              <label>Aspect ratio</label>
              <select id="aspect">
                <option value="1024x1024">1:1 – 1024×1024</option>
                <option value="1344x768">16:9 – 1344×768</option>
                <option value="768x1344">9:16 – 768×1344</option>
              </select>
            </div>
            <div style="flex:1">
              <label>Number of images</label>
              <!-- Kept for UI completeness, but backend forces n=1 for DALL·E 3 -->
              <input id="count" type="number" min="1" max="1" value="1" />
            </div>
          </div>

          <div style="display:flex;gap:10px;margin-top:12px;align-items:center">
            <button id="generate">Generate</button>
            <button id="reset" type="button">Reset</button>
            <label style="margin-left:auto;font-size:12px;display:flex;align-items:center;gap:4px">
              <input id="demo" type="checkbox"> Demo mode
            </label>
          </div>

          <div id="error" class="error" style="display:none;margin-top:12px"></div>
        </div>

        <!-- Right results -->
        <div class="card">
          <h3 style="margin-top:0">Results</h3>
          <div id="empty">Images will appear here.</div>
          <div id="gallery" class="gallery" style="display:none"></div>
        </div>
      </div>
    </div>

    <script>
      const el = (id) => document.getElementById(id);
      const gallery = el("gallery");
      const empty = el("empty");
      const errBox = el("error");

      const parseWH = (v) => {
        const [w, h] = v.split("x").map(Number);
        return { width: w, height: h };
      };

      el("reset").addEventListener("click", () => {
        el("prompt").value = "";
        el("neg").value = "";
        el("aspect").value = "1024x1024";
        el("count").value = 1;
        gallery.innerHTML = "";
        gallery.style.display = "none";
        empty.style.display = "block";
        errBox.style.display = "none";
      });

      function showImages(images) {
        gallery.innerHTML = "";
        images.forEach((img, i) => {
          const d = document.createElement("div");
          d.className = "thumb";
          d.innerHTML = `
            <img src="${img.url}" alt="generated ${i+1}">
            <div class="actions">
              <button onclick="window.open('${img.url}', '_blank')">Open</button>
              <button onclick="downloadImage('${img.url}', ${i})">Download</button>
            </div>`;
          gallery.appendChild(d);
        });
        gallery.style.display = "grid";
        empty.style.display = "none";
      }

      el("generate").addEventListener("click", async () => {
        const prompt = el("prompt").value.trim();
        const neg = el("neg").value.trim();
        const {width, height} = parseWH(el("aspect").value);
        const count = Math.max(1, Math.min(4, Number(el("count").value)));
        const demo = el("demo").checked;

        errBox.style.display = "none";
        empty.textContent = "Generating…";

        try {
          let images = [];
          if (demo) {
            // DEMO: random placeholders from picsum
            images = Array.from({ length: count }).map((_, i) => ({
              url: `https://picsum.photos/${width}/${height}?random=${Date.now()}_${i}`
            }));
          } else {
            const res = await fetch("/api/generate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ prompt, negativePrompt: neg, width, height, count })
            });
            const text = await res.text();
            let payload = {};
            try { payload = JSON.parse(text); } catch { /* plain text */ }
            if (!res.ok) throw new Error(payload.error || text || "Generate failed");
            if (!payload.images?.length) throw new Error("No images returned");
            images = payload.images;
          }
          showImages(images);
        } catch (e) {
          errBox.textContent = e.message || "Generation failed";
          errBox.style.display = "block";
          empty.textContent = "Images will appear here.";
        }
      });

      // Robust download: data URLs direct, others via backend proxy (CORS-safe)
      async function downloadImage(url, i = 0) {
        try {
          if (url.startsWith("data:")) {
            const a = document.createElement("a");
            a.href = url;
            a.download = `image-${i + 1}.png`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            return;
          }
          const resp = await fetch(`/api/download?u=${encodeURIComponent(url)}`);
          if (!resp.ok) throw new Error("Download failed");
          const blob = await resp.blob();
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `image-${i + 1}.png`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        } catch (e) {
          alert("Download failed — opening in a new tab.");
          window.open(url, "_blank");
        }
      }
    </script>
  </body>
</html>'''

@app.get("/")
def index():
    resp = make_response(HTML)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

@app.post("/api/generate")
def generate():
    if not client:
        return jsonify({"error": "OPENAI_API_KEY missing. Use Demo mode."}), 500
    try:
        data = request.get_json(force=True) or {}
        prompt = (data.get("prompt") or "").strip()
        neg = (data.get("negativePrompt") or "").strip()
        w = int(data.get("width") or 1024)
        h = int(data.get("height") or 1024)
        # UI may send 'count', but DALL·E 3 only supports n=1 per request
        if not prompt:
            return jsonify({"error": "Prompt is required."}), 400

        # Model: default to DALL·E 3 unless overridden
        model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

        # DALL·E 3 allowed sizes: 1024x1024, 1792x1024 (landscape), 1024x1792 (portrait)
        ar = w / h
        if ar > 1.2:
            size = "1792x1024"
        elif ar < 0.83:
            size = "1024x1792"
        else:
            size = "1024x1024"

        full = f"{prompt} --no {neg}" if neg else prompt

        # Always request one image to avoid 400 errors with DALL·E 3
        resp = client.images.generate(
            model=model,
            prompt=full,
            size=size,
            n=1,
        )

        images = []
        for d in resp.data:
            if getattr(d, "b64_json", None):
                images.append({"url": f"data:image/png;base64,{d.b64_json}"})
            elif getattr(d, "url", None):
                images.append({"url": d.url})

        if not images:
            return jsonify({"error": "No images returned"}), 502

        return jsonify({"images": images})

    except Exception as e:
        print("IMAGE GEN ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500

# Download proxy (fixes CORS/redirect issues for external image URLs)
@app.get("/api/download")
def download_proxy():
    url = request.args.get("u", "")
    if not url:
        return jsonify({"error": "missing url"}), 400
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "application/octet-stream")
        ext = (
            "png" if "png" in ctype else
            "jpg" if ("jpeg" in ctype or "jpg" in ctype) else
            "webp" if "webp" in ctype else
            "bin"
        )
        resp = Response(data, mimetype=ctype)
        resp.headers["Content-Disposition"] = f"attachment; filename=image.{ext}"
        resp.headers["Cache-Control"] = "no-store"
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 Running: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


