# Amazon product scraper with LLM-based description improvement (English, currency-safe).
# Add currency support
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, JsonCssExtractionStrategy
from openai import OpenAI


# ---------- SELECTOR DEFINITIONS ----------

@dataclass
class Selectors:
    product_name: str
    # Price helpers (use any that exist)
    currency_symbol: str
    price: str
    price_whole: str
    price_fraction: str
    review_rating: str
    description: str

# Safe static demo (Books to Scrape)
BOOKS = Selectors(
    product_name="div.product_main h1",
    currency_symbol="p.price_color",          # includes symbol (e.g. £)
    price="p.price_color",
    price_whole="",
    price_fraction="",
    review_rating="p.star-rating",            # class encodes stars; normalized later
    description="div#product_description ~ p",
)

# Amazon (common selectors; DOM can vary)
AMAZON = Selectors(
    product_name="span#productTitle",
    currency_symbol="span.a-price-symbol",
    price="span.a-price > span.a-offscreen, span.priceToPay span.a-offscreen, span.apexPriceToPay span.a-offscreen",
    price_whole="span.a-price-whole",
    price_fraction="span.a-price-fraction",
    review_rating="span[data-hook='rating-out-of-text'], i.a-icon-star span.a-icon-alt",
    description="div#feature-bullets ul",
)

# AliExpress (varies a lot; best-effort)
ALIEXPRESS = Selectors(
    product_name="h1.product-title-text, h1.product-title",
    currency_symbol="span.product-price-symbol, span#j-sku-price, span#j-sku-price strong",
    price="div.product-price-current span.product-price-value, span.product-price-value",
    price_whole="",
    price_fraction="",
    review_rating="span.reviewer-rating, span.product-reviewer-soldinfo, span#j-customer-reviews",
    description="div.product-description, div#product-description, div.product-specs",
)


def pick_selectors(url: str) -> Selectors:
    u = url.lower()
    if "amazon." in u:
        return AMAZON
    if "aliexpress." in u:
        return ALIEXPRESS
    return BOOKS


# ---------- UTILITIES ----------

def guess_decimal_comma(url: str) -> bool:
    """Heuristics: .de, .fr, .es, .it usually use decimal comma."""
    host = urlparse(url).hostname or ""
    return any(host.endswith(tld) for tld in (".de", ".fr", ".es", ".it", ".nl", ".fi"))

def clean_space(s: str | None) -> str:
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s).strip()

def build_price(url: str, raw_price: str, symbol: str, whole: str, frac: str) -> str | None:
    """
    Build a normalized visible price string:
      - Prefer raw_price if it already contains currency + amount (e.g., '€7,99' or 'EUR 7,99').
      - Otherwise construct from symbol + whole + fraction.
    """
    rp = clean_space(raw_price)
    sym = clean_space(symbol)
    wh  = clean_space(whole)
    fr  = clean_space(frac)

    # If raw price already looks complete, use it as-is
    if rp:
        # remove hidden chars
        rp = rp.replace("\u202f", " ").replace("\xa0", " ")
        return rp

    if not (sym or wh):
        return None

    # Amazon sometimes returns '7.' as whole and '99' as fraction
    wh = wh.rstrip("., ").replace("\u202f", "").replace("\xa0", "")
    fr = fr.replace("\u202f", "").replace("\xa0", "")

    use_comma = guess_decimal_comma(url)
    dec = "," if use_comma else "."

    if fr:
        amount = f"{wh}{dec}{fr}"
    else:
        amount = wh

    return f"{sym}{amount}".strip()


# ---------- SCRAPER ----------

async def scrape_product_info(url: str, selectors: Selectors) -> dict:
    print(f"\n[info] Crawling: {url}")

    extraction_schema = {
        "baseSelector": "body",
        "fields": [
            {"name": "product_name",   "selector": selectors.product_name,   "type": "text"},
            {"name": "currency_symbol","selector": selectors.currency_symbol, "type": "text"},
            {"name": "price",          "selector": selectors.price,          "type": "text"},
            {"name": "price_whole",    "selector": selectors.price_whole,    "type": "text"},
            {"name": "price_fraction", "selector": selectors.price_fraction,  "type": "text"},
            {"name": "review_rating",  "selector": selectors.review_rating,  "type": "text"},
            {"name": "description",    "selector": selectors.description,    "type": "text"},
        ],
    }

    run_cfg = CrawlerRunConfig(
        extraction_strategy=JsonCssExtractionStrategy(schema=extraction_schema)
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=run_cfg)

    if getattr(result, "success", True) is False:
        return {"error": getattr(result, "error_message", "crawl failed")}

    raw = getattr(result, "extracted_content", None) or getattr(result, "structured_data", None)
    if not raw:
        return {"error": "empty extraction"}

    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception as e:
            return {"error": f"json parse failed: {e}"}
    else:
        data = raw

    if isinstance(data, list):
        data = data[0] if data else {}

    # Cleanup
    for k in ("product_name", "currency_symbol", "price", "price_whole", "price_fraction", "review_rating", "description"):
        if k in data:
            data[k] = clean_space(data[k])

    # Normalize rating to "x.y out of 5" when we can
    rr = data.get("review_rating", "")
    if rr:
        m = re.search(r"([0-5](?:[.,]\d)?)\s*(?:out of|/)\s*5", rr, re.I)
        if m:
            val = m.group(1).replace(",", ".")
            data["review_rating"] = f"{val} out of 5"
        elif rr.startswith("star-rating"):
            m2 = re.search(r"star-rating\s+(\w+)", rr, re.I)
            map_ = {"One":"1", "Two":"2", "Three":"3", "Four":"4", "Five":"5"}
            if m2 and m2.group(1) in map_:
                data["review_rating"] = f"{map_[m2.group(1)]} out of 5"

    # Build final visible price
    final_price = build_price(
        url,
        data.get("price", ""),
        data.get("currency_symbol", ""),
        data.get("price_whole", ""),
        data.get("price_fraction", ""),
    )
    data["price"] = final_price or ""

    # Strip helpers from output
    data.pop("currency_symbol", None)
    data.pop("price_whole", None)
    data.pop("price_fraction", None)

    # Final sanity
    if not any(data.get(k) for k in ("product_name", "price", "review_rating", "description")):
        return {"error": "selectors did not match any content"}

    data["source_url"] = url
    return data


# ---------- LLM IMPROVER (EN, CURRENCY-SAFE) ----------

def improve_description_en(product: dict) -> str:
    """
    Produce an improved English product description that **must** keep the price string and currency as-is.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "ERROR: OPENAI_API_KEY environment variable is missing."

    client = OpenAI(api_key=api_key)

    name = product.get("product_name") or "Unknown product"
    price = product.get("price") or "N/A"
    rating = product.get("review_rating") or "N/A"
    desc  = product.get("description") or ""

    prompt = f"""
You are a senior e-commerce copywriter. Rewrite the product description in **English**.

Input:
- Name: {name}
- Price (exact string): {price}
- Review rating: {rating}
- Existing description: {desc}

Strict rules:
- Always write in English.
- If you mention the price, you MUST repeat it **exactly** as shown above (same currency symbol/format). Do NOT convert currency or change separators.
- 120–200 words.
- Focus on buyer benefits; do not invent specs you don't have.
- If rating is high and price is low/moderate, emphasize value-for-money; if price is higher, justify with quality/benefits.
- No title; start directly with the paragraph.
""".strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You always respond in English and follow currency constraints precisely."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=350,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"ERROR: OpenAI call failed: {e}"

    # Safety post-fix: if LLM used a wrong $/£/€ symbol, replace with one from the price string
    currency_in_price = None
    for sym in ("€", "£", "$", "EUR", "GBP", "USD"):
        if sym in price:
            currency_in_price = sym
            break
    if currency_in_price:
        # if model used a different common symbol, normalize
        wrong_syms = {"€": ["$", "USD"], "£": ["$", "USD", "EUR", "€"], "$": ["€", "EUR", "£", "GBP"]}
        for wrong in wrong_syms.get(currency_in_price, []):
            if wrong in text and currency_in_price not in text:
                text = text.replace(wrong, currency_in_price)

    return text


# ---------- RUN ONCE + INTERACTIVE LOOP ----------

def run_once(url: str):
    if not (url.startswith("http://") or url.startswith("https://")):
        print('ERROR: URL must start with "http://" or "https://".')
        return

    selectors = pick_selectors(url)
    scraped = asyncio.run(scrape_product_info(url, selectors))

    if "error" in scraped:
        print(json.dumps({"error": scraped["error"], "source_url": url}, indent=2, ensure_ascii=False))
        return

    improved = improve_description_en(scraped)
    output = {
        "source_url": scraped.get("source_url"),
        "product_name": scraped.get("product_name"),
        "price": scraped.get("price"),
        "review_rating": scraped.get("review_rating"),
        "description": scraped.get("description"),
        "improved_description": improved,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    print("Product Scraper (English) — enter a product URL. Quit with 'q'.")
    print("Tip: test first with https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html\n")
    try:
        while True:
            url = input("URL (or 'q' to quit): ").strip()
            if not url:
                continue
            if url.lower() == "q":
                print("Bye.")
                break
            run_once(url)
            nxt = input("\nEnter another URL or 'q' to quit: ").strip()
            if nxt.lower() == "q":
                print("Bye.")
                break
            if nxt:
                run_once(nxt)
    except KeyboardInterrupt:
        print("\nInterrupted. Bye.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_once(sys.argv[1])
    else:
        main()
