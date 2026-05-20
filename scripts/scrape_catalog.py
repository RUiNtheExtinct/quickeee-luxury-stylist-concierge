from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from html import unescape
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import CatalogItem, Category  # noqa: E402


BRANDS = [
    {
        "brand": "Everlane",
        "source": "https://www.everlane.com",
        "products_url": "https://www.everlane.com/products.json?limit=250",
    },
    {
        "brand": "Taylor Stitch",
        "source": "https://www.taylorstitch.com",
        "products_url": "https://www.taylorstitch.com/products.json?limit=250",
    },
    {
        "brand": "Koio",
        "source": "https://www.koio.co",
        "products_url": "https://www.koio.co/products.json?limit=250",
    },
    {
        "brand": "Nisolo",
        "source": "https://nisolo.com",
        "products_url": "https://nisolo.com/products.json?limit=250",
    },
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
]

TOP_KEYWORDS = {
    "tee",
    "t-shirt",
    "tshirt",
    "shirt",
    "polo",
    "henley",
    "sweater",
    "sweatshirt",
    "hoodie",
    "jacket",
    "blazer",
    "overshirt",
    "top",
}

BOTTOM_KEYWORDS = {
    "pant",
    "pants",
    "trouser",
    "trousers",
    "chino",
    "jean",
    "denim",
    "short",
    "shorts",
}

SHOE_KEYWORDS = {"shoe", "sneaker", "loafer", "boot", "sandal", "slide", "moc", "huarache", "oxford"}
ACCESSORY_KEYWORDS = {
    "accessory",
    "accessories",
    "bag",
    "belt",
    "beanie",
    "cap",
    "charm",
    "cuff",
    "hat",
    "scarf",
    "sock",
    "socks",
    "tote",
    "wallet",
}

COLOR_WORDS = [
    "black",
    "blue",
    "brown",
    "charcoal",
    "cream",
    "ecru",
    "green",
    "grey",
    "gray",
    "indigo",
    "ivory",
    "khaki",
    "navy",
    "olive",
    "sand",
    "stone",
    "tan",
    "white",
]

MATERIAL_WORDS = ["linen", "cotton", "nubuck", "suede", "leather", "canvas", "denim", "wool", "cashmere", "silk"]


async def scrape_shopify_catalog(delay_min: float, delay_max: float, timeout: float) -> list[CatalogItem]:
    items: list[CatalogItem] = []
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for brand in BRANDS:
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            response = await client.get(
                brand["products_url"],
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            response.raise_for_status()
            payload = response.json()
            for product in payload.get("products", []):
                item = normalize_product(brand, product)
                if item:
                    items.append(item)
    return dedupe(items)


def normalize_product(brand: dict[str, str], product: dict[str, Any]) -> CatalogItem | None:
    title = clean(product.get("title", ""))
    product_type = clean(product.get("product_type", ""))
    tags = [clean(tag).lower() for tag in product.get("tags", []) if clean(tag)]
    haystack = " ".join([title, product_type, *tags]).lower()
    category = classify(haystack)
    if category is None:
        return None

    variants = product.get("variants") or []
    first_variant = variants[0] if variants else {}
    price = parse_price(first_variant.get("price"))
    if price <= 0:
        return None

    image_url = choose_image_url(product)

    description = html_to_text(product.get("body_html", ""))
    handle = product.get("handle", "")
    product_url = f"{brand['source'].rstrip('/')}/products/{handle}" if handle else brand["source"]
    item_id = stable_id(f"{brand['brand']}:{product.get('id')}:{title}")

    return CatalogItem(
        id=item_id,
        brand=brand["brand"],
        source=brand["source"],
        name=title,
        price=price,
        currency="USD",
        image_url=image_url or "https://placehold.co/800x1000?text=Quickeee",
        product_url=product_url,
        category=category,
        description=description or f"{title} from {brand['brand']}.",
        color=extract_color(haystack),
        material=extract_material(" ".join([haystack, description.lower()])),
        tags=tags[:20],
    )


async def scrape_with_playwright(collection_urls: list[str]) -> list[dict[str, str]]:
    """Optional DOM scraper for JS-heavy pages.

    This is intentionally generic: it scrolls, waits between actions, and reads
    JSON-LD/product-card text. It is useful when a brand blocks products.json or
    renders inventory behind client-side state.
    """

    from playwright.async_api import async_playwright

    records: list[dict[str, str]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS), locale="en-US")
        page = await context.new_page()
        for url in collection_urls:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            for _ in range(6):
                await page.mouse.wheel(0, 1800)
                await page.wait_for_timeout(random.randint(700, 1800))
            cards = await page.locator("[data-product-id], article, .product-card, [class*=product]").all()
            for card in cards[:120]:
                text = clean(await card.inner_text(timeout=1000))
                image = ""
                img = card.locator("img").first
                if await img.count():
                    image = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
                if text:
                    records.append({"source_url": url, "text": text, "image_url": image})
        await browser.close()
    return records


def classify(text: str) -> Category | None:
    if any(keyword in text for keyword in TOP_KEYWORDS):
        return Category.top
    if any(keyword in text for keyword in BOTTOM_KEYWORDS):
        return Category.bottom
    if any(keyword in text for keyword in SHOE_KEYWORDS):
        return Category.shoe
    if any(keyword in text for keyword in ACCESSORY_KEYWORDS):
        return Category.accessory
    return None


def choose_image_url(product: dict[str, Any]) -> str:
    images = product.get("images") or []
    if not images:
        return ""
    ranked = sorted(images, key=image_rank, reverse=True)
    image_url = ranked[0].get("src") or ""
    if image_url.startswith("//"):
        image_url = "https:" + image_url
    return image_url


def image_rank(image: dict[str, Any]) -> tuple[int, int]:
    src = str(image.get("src") or "").lower()
    alt = str(image.get("alt") or "").lower()
    text = f"{src} {alt}"
    score = 0
    if "placehold.co" in text or "placeholder" in text:
        score -= 100
    if any(term in text for term in ["swatch", "fabric", "detail", "texture", "overhead_single"]):
        score -= 12
    if any(term in text for term in ["pair", "portrait", "pdp_01", "-1", "_1", "front", "angled"]):
        score += 8
    width = int(image.get("width") or 0)
    height = int(image.get("height") or 0)
    area = width * height
    if width and height:
        ratio = height / width
        if 0.8 <= ratio <= 1.8:
            score += 4
    return score, area


def extract_color(text: str) -> str:
    for color in COLOR_WORDS:
        if re.search(rf"\b{re.escape(color)}\b", text):
            return "grey" if color == "gray" else color
    return "unknown"


def extract_material(text: str) -> str:
    for material in MATERIAL_WORDS:
        if re.search(rf"\b{re.escape(material)}\b", text):
            return material
    return "unknown"


def parse_price(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        numeric = float(value)
        return numeric / 100 if numeric >= 1000 else numeric
    match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    numeric = float(match.group(0)) if match else 0.0
    return numeric / 100 if numeric >= 1000 else numeric


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    return clean(unescape(soup.get_text(" ")))


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def dedupe(items: list[CatalogItem]) -> list[CatalogItem]:
    seen: set[str] = set()
    deduped: list[CatalogItem] = []
    for item in items:
        key = f"{item.brand}:{item.name}:{item.color}:{item.category}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape public apparel catalogs into clean JSON.")
    parser.add_argument("--output", default="data/catalog.live.json")
    parser.add_argument("--delay-min", type=float, default=0.8)
    parser.add_argument("--delay-max", type=float, default=2.2)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    items = await scrape_shopify_catalog(args.delay_min, args.delay_max, args.timeout)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([item.model_dump(mode="json") for item in items], indent=2))
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category.value] = counts.get(item.category.value, 0) + 1
    print(f"Wrote {len(items)} items to {output}: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
