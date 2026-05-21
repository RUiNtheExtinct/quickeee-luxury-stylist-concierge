"""Unit tests for the scraper's structured extraction.

These guard the data-quality fixes: gender is derived from product_type/handle/tags
(not the display name), and color prefers Shopify's structured color tags/options over
a naive first-keyword scan of free text (which previously mislabeled a gold sandal as
"black").
"""

from app.models import Gender
from scripts.scrape_catalog import (
    color_from_tags,
    detect_gender,
    extract_color,
    material_from_tags,
    normalize_product,
)

BRAND = {"brand": "Taylor Stitch", "source": "https://www.taylorstitch.com"}


def test_color_from_structured_tags_beats_free_text():
    # 'Primary Color: Green' must win even though other words appear in the haystack.
    assert color_from_tags(["MENS", "Primary Color: Green", "Color:Green"]) == "green"
    assert color_from_tags(["color-greige"]) == "stone"
    assert color_from_tags(["Material:Organic Cotton"]) == ""


def test_material_from_structured_tags():
    assert material_from_tags(["Primary Material: Organic Cotton"]) == "cotton"
    assert material_from_tags(["Material:Linen"]) == "linen"


def test_extract_color_canonicalizes_and_uses_aliases():
    assert extract_color("Marigold") == "yellow"  # canonical map
    assert extract_color("Heathered Oat") == "cream"  # poetic alias
    assert extract_color("gray flannel") == "grey"
    assert extract_color("size large only") == ""  # no color present


def test_detect_gender_from_signals():
    assert detect_gender(product_type="Men's Leather Slip On", handle="mens-huarache", tags=[], source="x") == Gender.men
    assert (
        detect_gender(product_type="", handle="womens-huarache-2-0-marigold", tags=["women", "womens-sandals"], source="x")
        == Gender.women
    )
    assert detect_gender(product_type="", handle="canvas-tote", tags=[], source="x") == Gender.unisex


def test_normalize_product_fixes_the_gold_sandal_bug():
    # Reproduces the original failure: a women's gold sandal that scanned as "black".
    product = {
        "id": 123,
        "title": "Women's Huarache Sandal 2.0 Gold",
        "product_type": "Women's Leather Sandal",
        "handle": "womens-huarache-sandal-2-0-gold",
        "tags": ["women", "womens-sandals", "color-marigold"],
        "body_html": "<p>Hand-woven leather sandal with a black rubber outsole.</p>",
        "variants": [{"price": "138.00", "option1": "8"}],
        "images": [{"src": "https://cdn.example.com/gold_pair.jpg", "width": 1000, "height": 1200}],
        "options": [{"name": "Size", "position": 1, "values": ["8", "9"]}],
    }
    item = normalize_product(BRAND, product)
    assert item is not None
    assert item.gender == Gender.women
    assert item.category.value == "shoe"
    # Color must come from the structured 'color-marigold' tag, not the word "black"
    # in the description.
    assert item.color != "black"
    assert item.color == "yellow"
