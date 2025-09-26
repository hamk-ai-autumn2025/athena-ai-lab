# materials/ai_images.py
import os, base64
from openai import OpenAI

def generate_image(prompt: str, size: str = "1024x1024") -> bytes | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    client = OpenAI(api_key=api_key)
    # gpt-image-1 palauttaa base64
    resp = client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
    b64 = resp.data[0].b64_json
    return base64.b64decode(b64)
