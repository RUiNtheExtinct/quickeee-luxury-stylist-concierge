from __future__ import annotations

import hashlib
import json
from itertools import cycle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BRANDS = ["Everlane", "Taylor Stitch", "Sunspel", "Aurelien", "Orlebar Brown"]
SOURCES = {
    "Everlane": "https://www.everlane.com",
    "Taylor Stitch": "https://www.taylorstitch.com",
    "Sunspel": "https://www.sunspel.com",
    "Aurelien": "https://aurelien-online.com",
    "Orlebar Brown": "https://www.orlebarbrown.com",
}

TOPS = [
    ("Sea Island Cotton Tee", "white", "cotton", 68, "crisp crew neck tee with a smooth handfeel for warm resort evenings"),
    ("Linen Camp Collar Shirt", "ecru", "linen", 118, "open collar linen shirt cut for breezy summer dinners"),
    ("Pima Jersey Polo", "navy", "cotton", 88, "refined polo with a clean placket and tailored sleeve"),
    ("Garment Dyed Oxford Shirt", "blue", "cotton", 98, "soft oxford shirt that balances polish with relaxed texture"),
    ("Resort Knit Polo", "cream", "cotton", 128, "fine gauge knit polo for yacht decks and terrace cocktails"),
    ("Linen Popover", "sand", "linen", 132, "light popover shirt with a coastal profile"),
    ("Supima Pocket Tee", "olive", "cotton", 58, "minimal pocket tee in compact cotton jersey"),
    ("Merino Travel Tee", "charcoal", "wool", 96, "temperature regulating tee with an elevated drape"),
    ("Cotton Henley", "grey", "cotton", 74, "three button henley for casual layered styling"),
    ("Silk Cotton Resort Shirt", "ivory", "silk", 148, "quietly lustrous shirt for a luxurious warm weather look"),
]

BOTTOMS = [
    ("Italian Chino Trouser", "navy", "cotton", 138, "tailored chino with a clean taper and refined waistband"),
    ("Linen Drawstring Trouser", "stone", "linen", 158, "relaxed linen trouser that still reads elegant"),
    ("Pleated Cotton Short", "khaki", "cotton", 92, "tailored short with a sharp pleat and summer weight cloth"),
    ("Garment Dyed Jean", "indigo", "denim", 128, "slim straight denim with a deep indigo wash"),
    ("Travel Tech Trouser", "charcoal", "cotton", 148, "crease resistant trouser for long days and evening plans"),
    ("Resort Linen Short", "white", "linen", 110, "polished linen short for beach clubs and yacht decks"),
    ("Canvas Officer Pant", "olive", "cotton", 126, "structured canvas pant with utilitarian restraint"),
    ("Cotton Gurkha Trouser", "tan", "cotton", 168, "high waisted trouser with a sartorial side adjuster"),
    ("Seersucker Drawstring Pant", "blue", "cotton", 142, "light textured pant for humid summer settings"),
    ("Washed Twill Chino", "sand", "cotton", 118, "versatile twill chino with a soft broken-in finish"),
]

SHOES = [
    ("Suede Penny Loafer", "brown", "suede", 220, "unlined loafer that sharpens casual tailoring"),
    ("Minimal Leather Sneaker", "white", "leather", 180, "low profile sneaker with clean luxury lines"),
    ("Espadrille Slip-On", "sand", "canvas", 120, "rope sole slip-on for warm resort dressing"),
    ("Boat Deck Loafer", "tan", "leather", 190, "flexible deck loafer with quiet nautical energy"),
    ("Woven Leather Sandal", "brown", "leather", 160, "refined sandal for poolside dinners and linen trousers"),
    ("Driving Moccasin", "navy", "suede", 175, "soft driving shoe that pairs naturally with chinos"),
]

ACCESSORIES = [
    ("Silk Pocket Square", "ivory", "silk", 48, "hand rolled pocket square for soft contrast against tailoring"),
    ("Braided Leather Belt", "brown", "leather", 78, "supple braided belt that relaxes a tailored trouser"),
    ("Linen Bandana", "navy", "linen", 34, "lightweight bandana for coastal styling"),
    ("Woven Panama Hat", "sand", "straw", 120, "structured summer hat for resort and beach club dressing"),
    ("Suede Weekender Bag", "tan", "suede", 310, "compact weekender that completes a travel uniform"),
    ("Brushed Silver Cuff", "silver", "metal", 96, "minimal cuff with a quiet jewelry finish"),
    ("Cashmere Travel Scarf", "grey", "cashmere", 155, "soft travel scarf for cool evenings after warm days"),
    ("Canvas Tote", "olive", "canvas", 88, "structured tote with a utilitarian luxury attitude"),
]


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def image_url(category: str, color: str, idx: int) -> str:
    palette = {
        "white": "f7f4ec",
        "ecru": "ebe3d0",
        "cream": "efe6d3",
        "ivory": "f4efe4",
        "sand": "d8c09a",
        "stone": "b9b2a3",
        "tan": "a98259",
        "khaki": "a59673",
        "brown": "6d4d34",
        "navy": "172a4a",
        "blue": "5c7fa3",
        "indigo": "263f72",
        "olive": "596145",
        "charcoal": "34373a",
        "grey": "8a8f91",
        "black": "191919",
    }
    bg = palette.get(color, "d4d4d4")
    label = f"{category.title()}+{idx}"
    return f"https://placehold.co/900x1200/{bg}/ffffff?text={label}"


def build_items() -> list[dict]:
    items: list[dict] = []
    brand_cycle = cycle(BRANDS)
    for category, base_items, target in [
        ("top", TOPS, 160),
        ("bottom", BOTTOMS, 120),
        ("shoe", SHOES, 45),
        ("accessory", ACCESSORIES, 40),
    ]:
        for idx in range(target):
            name, color, material, price, description = base_items[idx % len(base_items)]
            brand = next(brand_cycle)
            seasonal_name = f"{name} {idx // len(base_items) + 1}" if idx >= len(base_items) else name
            item_id = stable_id(f"{brand}:{category}:{seasonal_name}:{color}:{idx}")
            items.append(
                {
                    "id": item_id,
                    "brand": brand,
                    "source": SOURCES[brand],
                    "name": seasonal_name,
                    "price": float(price + (idx % 5) * 7),
                    "currency": "USD",
                    "image_url": image_url(category, color, idx + 1),
                    "product_url": f"{SOURCES[brand]}/products/{item_id}",
                    "category": category,
                    "description": description,
                    "color": color,
                    "material": material,
                    "tags": [
                        category,
                        color,
                        material,
                        "luxury",
                        "summer" if material in {"linen", "cotton", "canvas"} else "premium",
                        "resort" if color in {"white", "ecru", "cream", "sand", "navy"} else "city",
                    ],
                }
            )
    return items


def build_from_live_scrape() -> list[dict] | None:
    live_path = ROOT / "data/catalog.live.json"
    if not live_path.exists():
        live_path = ROOT / "data/catalog.scraped.sample.json"
    if not live_path.exists():
        return None
    live_items = json.loads(live_path.read_text())
    live_items = [item for item in live_items if has_usable_image(item)]
    tops = select_balanced(live_items, "top", 160, ["tee", "shirt", "polo", "henley", "popover", "sweater"])
    bottoms = select_balanced(live_items, "bottom", 120, ["pant", "trouser", "chino", "jean", "short"])
    if len(tops) < 100 or len(bottoms) < 80:
        return None
    shoes = select_balanced(live_items, "shoe", 60, ["sneaker", "loafer", "sandal", "moc", "shoe", "boot"])
    accessories = select_balanced(
        live_items,
        "accessory",
        80,
        ["belt", "bag", "tote", "cap", "hat", "beanie", "scarf", "sock", "charm", "wallet"],
    )
    generated = build_items()
    if len(shoes) < 28:
        shoes = [item for item in generated if item["category"] == "shoe"]
    return interleave_collections([tops, bottoms, shoes, accessories])


def has_usable_image(item: dict) -> bool:
    image_url = item.get("image_url", "")
    if not image_url:
        return False
    blocked = ["placehold.co", "placeholder", "quickeee"]
    return not any(term in image_url.lower() for term in blocked)


def select_balanced(items: list[dict], category: str, target: int, preferred_terms: list[str]) -> list[dict]:
    brands = sorted({item["brand"] for item in items})
    picked: list[dict] = []
    seen: set[str] = set()
    excluded_terms = {"dress", "skirt", "bodysuit", "legging", "care bundle", "cleaner", "insole", "laces"}
    per_brand = max(1, target // max(1, len(brands)))
    for brand in brands:
        candidates = [
            item
            for item in items
            if item.get("brand") == brand
            and item.get("category") == category
            and not any(term in item.get("name", "").lower() for term in excluded_terms)
            and any(term in item.get("name", "").lower() for term in preferred_terms)
        ]
        for item in candidates[:per_brand]:
            picked.append(item)
            seen.add(item["id"])
    for item in items:
        if len(picked) >= target:
            break
        if (
            item.get("category") == category
            and item["id"] not in seen
            and not any(term in item.get("name", "").lower() for term in excluded_terms)
        ):
            picked.append(item)
            seen.add(item["id"])
    return picked[:target]


def interleave_collections(collections: list[list[dict]]) -> list[dict]:
    interleaved: list[dict] = []
    max_length = max(len(collection) for collection in collections)
    for index in range(max_length):
        for collection in collections:
            if index < len(collection):
                interleaved.append(collection[index])
    return interleaved


def main() -> None:
    output = ROOT / "data/catalog.seed.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    items = build_from_live_scrape() or build_items()
    output.write_text(json.dumps(items, indent=2))
    counts: dict[str, int] = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    print(f"Wrote {len(items)} seed items to {output}: {counts}")


if __name__ == "__main__":
    main()
