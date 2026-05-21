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

from app.models import CatalogItem, Category, Gender  # noqa: E402


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
    "hat",
    "scarf",
    "sock",
    "socks",
    "tote",
    "wallet",
}

# Ordered most-specific first so multi-word colors win before their base word.
COLOR_WORDS = [
    "off white",
    "navy",
    "indigo",
    "charcoal",
    "burgundy",
    "maroon",
    "marigold",
    "mustard",
    "camel",
    "khaki",
    "olive",
    "forest",
    "sage",
    "greige",
    "taupe",
    "beige",
    "stone",
    "sand",
    "ecru",
    "ivory",
    "cream",
    "bone",
    "oatmeal",
    "natural",
    "tan",
    "rust",
    "terracotta",
    "coral",
    "blush",
    "pink",
    "red",
    "orange",
    "yellow",
    "gold",
    "green",
    "teal",
    "blue",
    "purple",
    "lavender",
    "brown",
    "chocolate",
    "coffee",
    "grey",
    "gray",
    "silver",
    "black",
    "white",
]

# Map noisy color names onto a compact, stylable palette the agent reasons over.
COLOR_CANONICAL = {
    "gray": "grey",
    "silver": "grey",
    "off white": "white",
    "bone": "ivory",
    "oatmeal": "cream",
    "natural": "ecru",
    "beige": "tan",
    "camel": "tan",
    "taupe": "tan",
    "greige": "stone",
    "coffee": "brown",
    "chocolate": "brown",
    "maroon": "burgundy",
    "marigold": "yellow",
    "mustard": "yellow",
    "gold": "yellow",
    "forest": "olive",
    "sage": "olive",
    "terracotta": "rust",
    "coral": "rust",
    "lavender": "purple",
}

MATERIAL_WORDS = [
    "linen",
    "organic cotton",
    "cotton",
    "nubuck",
    "suede",
    "leather",
    "canvas",
    "denim",
    "merino",
    "wool",
    "cashmere",
    "silk",
    "nylon",
    "fleece",
    "corduroy",
    "twill",
    "chambray",
]

# Poetic brand color names (mostly Everlane) mapped onto the stylable palette.
COLOR_ALIASES = {
    "birch": "cream",
    "beech": "tan",
    "parchment": "cream",
    "canvas": "ecru",
    "bone": "ivory",
    "aleutian": "blue",
    "skywriting": "blue",
    "heather rose": "pink",
    "passion fruit": "pink",
    "pale peach": "blush",
    "velvet morning": "navy",
    "graystone": "grey",
    "tungsten": "grey",
    "kalamata": "olive",
    "mayfly": "olive",
    "heathered oat": "cream",
    "heathered oats": "cream",
    "oat": "cream",
    "oatmeal": "cream",
    "espresso": "brown",
    "cabernet": "burgundy",
    "vintage indigo": "indigo",
    "avorio": "ivory",
    "wind": "grey",
}

WOMEN_SIGNALS = ("women", "woman", "womens", "women's", "ladies", "female")
MEN_SIGNALS = ("men", "mens", "men's", "male", "guys")


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
    handle = product.get("handle", "")
    raw_tags = [clean(tag) for tag in product.get("tags", []) if clean(tag)]
    tags = [tag.lower() for tag in raw_tags]
    haystack = " ".join([title, product_type, handle, *tags]).lower()
    category = classify(haystack)
    if category is None:
        return None

    variants = product.get("variants") or []
    first_variant = variants[0] if variants else {}
    price = parse_price(first_variant.get("price"))
    if price <= 0:
        return None

    image_url = choose_image_url(product)
    if not image_url:
        return None

    description = html_to_text(product.get("body_html", ""))
    product_url = f"{brand['source'].rstrip('/')}/products/{handle}" if handle else brand["source"]
    item_id = stable_id(f"{brand['brand']}:{product.get('id')}:{title}")

    # Prefer explicit structured signals (option/variant color, tagged color/material)
    # over scanning free text, which is what produced wrong labels before.
    option_values = collect_option_values(product, variants)
    color = (
        color_from_tags(raw_tags)
        or extract_color(" ".join(option_values))
        or extract_color(f"{title} {handle}")
        or extract_color(description.lower())
        or "unknown"
    )
    material = (
        material_from_tags(raw_tags)
        or extract_material(" ".join([title.lower(), product_type.lower(), description.lower()]))
        or "unknown"
    )
    gender = detect_gender(product_type=product_type, handle=handle, tags=tags, source=brand["source"])

    return CatalogItem(
        id=item_id,
        brand=brand["brand"],
        source=brand["source"],
        name=title,
        price=price,
        currency="USD",
        image_url=image_url,
        product_url=product_url,
        category=category,
        gender=gender,
        description=description or f"{title} from {brand['brand']}.",
        color=color,
        material=material,
        tags=tags[:20],
    )


def collect_option_values(product: dict[str, Any], variants: list[dict[str, Any]]) -> list[str]:
    """Pull the human-readable color option label (e.g. "Marigold") from Shopify options."""

    values: list[str] = []
    color_positions = []
    for option in product.get("options") or []:
        name = str(option.get("name", "")).strip().lower()
        if name in {"color", "colour"}:
            color_positions.append(option.get("position"))
            values.extend(str(value) for value in option.get("values", []))
    if not values and variants:
        # Some feeds only name the variant; the color is usually option1.
        for variant in variants[:4]:
            for key in ("option1", "option2", "option3"):
                value = variant.get(key)
                if value and not _looks_like_size(str(value)):
                    values.append(str(value))
    return values


def _looks_like_size(value: str) -> bool:
    text = value.strip().lower()
    return bool(re.fullmatch(r"(xxs|xs|s|m|l|xl|xxl|\d{1,2}(\.\d)?(\s*-\s*\d{2})?)", text))


def color_from_tags(raw_tags: list[str]) -> str:
    """Read Shopify's structured color tags: 'Primary Color: Green', 'Color:Green', 'color-greige'."""

    for tag in raw_tags:
        lowered = tag.lower()
        match = re.match(r"(?:primary\s*)?colou?r\s*[:\-]\s*(.+)", lowered)
        if not match:
            continue
        color = extract_color(match.group(1))
        if color:
            return color
    return ""


def material_from_tags(raw_tags: list[str]) -> str:
    for tag in raw_tags:
        lowered = tag.lower()
        match = re.match(r"(?:primary\s*)?material\s*[:\-]\s*(.+)", lowered)
        if not match:
            continue
        material = extract_material(match.group(1))
        if material:
            return material
    return ""


def detect_gender(*, product_type: str, handle: str, tags: list[str], source: str) -> Gender:
    """Derive gender from the most reliable structured signals, not the display name."""

    type_l = product_type.lower()
    handle_l = handle.lower()
    if re.search(r"\bwomen|women's|womens|ladies\b", type_l) or handle_l.startswith(("womens-", "women-", "womens_")):
        return Gender.women
    if re.search(r"\bmen|men's|mens\b", type_l) or handle_l.startswith(("mens-", "men-", "mens_")):
        return Gender.men
    tag_text = " ".join(tags)
    has_women = any(re.search(rf"(^|[\s:_-]){sig}([\s:_-]|$)", tag_text) for sig in WOMEN_SIGNALS)
    has_men = any(re.search(rf"(^|[\s:_-]){sig}([\s:_-]|$)", tag_text) for sig in MEN_SIGNALS)
    if has_women and not has_men:
        return Gender.women
    if has_men and not has_women:
        return Gender.men
    if re.search(r"\bwomen|womens|ladies\b", handle_l):
        return Gender.women
    if re.search(r"\bmen|mens\b", handle_l):
        return Gender.men
    return Gender.unisex


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
    if has_keyword(text, SHOE_KEYWORDS):
        return Category.shoe
    if has_keyword(text, ACCESSORY_KEYWORDS):
        return Category.accessory
    if has_keyword(text, TOP_KEYWORDS):
        return Category.top
    if has_keyword(text, BOTTOM_KEYWORDS):
        return Category.bottom
    return None


def has_keyword(text: str, keywords: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords)


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
    text = text.lower()
    for alias, canonical in COLOR_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return canonical
    for color in COLOR_WORDS:
        if re.search(rf"\b{re.escape(color)}\b", text):
            return COLOR_CANONICAL.get(color, color)
    return ""


def extract_material(text: str) -> str:
    text = text.lower()
    for material in MATERIAL_WORDS:
        if re.search(rf"\b{re.escape(material)}\b", text):
            return "cotton" if material == "organic cotton" else material
    return ""


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
        key = f"{item.brand}:{item.name}:{item.color}:{item.category}:{item.gender}"
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
