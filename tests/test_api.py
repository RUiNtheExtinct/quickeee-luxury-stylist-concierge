from fastapi.testclient import TestClient

from app.main import app


def test_style_me_returns_structured_recommendation():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/style-me",
            json={
                "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?",
                "include_trace": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_items"]
    assert data["total_price"] > 0
    assert data["stylist_note"]
    assert data["token_strategy"]
    assert any(step["step"] == "intent" for step in data["trace"])


def test_catalog_has_assignment_minimums():
    with TestClient(app) as client:
        response = client.get("/health")
        catalog = client.get("/api/v1/catalog?limit=100")
        first_page = client.get("/api/v1/catalog?limit=4&offset=0")
        second_page = client.get("/api/v1/catalog?limit=4&offset=4")

    assert response.status_code == 200
    assert response.json()["catalog_items"] >= 100
    assert catalog.status_code == 200
    categories = [item["category"] for item in catalog.json()]
    assert "top" in categories
    assert "bottom" in categories
    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert len(first_page.json()) == 4
    assert len(second_page.json()) == 4
    assert {item["id"] for item in first_page.json()}.isdisjoint({item["id"] for item in second_page.json()})


def test_tech_nerdy_party_prompt_drives_style_signals_and_accessory():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/style-me",
            json={
                "prompt": "I want to go to a suave tech bro party and want to look cool and nerdy.",
                "accessories": "on",
                "include_trace": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    intent_detail = next(step["detail"] for step in data["trace"] if step["step"] == "intent")
    assert "tech bro" in intent_detail
    assert "suave" in intent_detail
    assert "cool" in intent_detail
    assert "nerdy" in intent_detail
    # accessories=on forces the accessory slot.
    assert "accessory" in intent_detail
    assert any(item["category"] == "accessory" for item in data["recommended_items"])
    assert any(term in data["stylist_note"].lower() for term in ["tech", "nerdy", "suave"])


def test_recommended_items_carry_gender_and_are_coherent_for_women_brief():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/style-me",
            json={
                "prompt": "Style my wife a relaxed resort look for a beach club lunch with linen pieces.",
                "include_trace": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    intent_detail = next(step["detail"] for step in data["trace"] if step["step"] == "intent")
    assert "gender=women" in intent_detail
    # Every recommended piece must be women's or unisex — never men's.
    genders = {item["gender"] for item in data["recommended_items"]}
    assert genders, "expected at least one recommended item"
    assert "men" not in genders


def test_default_men_brief_never_returns_women_items():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/style-me",
            json={
                "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?",
                "include_trace": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    genders = {item["gender"] for item in data["recommended_items"]}
    assert "women" not in genders


def test_explicit_gender_override_wins_over_prompt_text():
    # Prompt says "girlfriend" but the explicit men override must win.
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/style-me",
            json={"prompt": "Style my girlfriend a chic dinner look.", "gender": "men"},
        )

    assert response.status_code == 200
    data = response.json()
    genders = {item["gender"] for item in data["recommended_items"]}
    assert "women" not in genders


def test_accessory_mode_off_and_on():
    with TestClient(app) as client:
        off = client.post(
            "/api/v1/style-me",
            json={"prompt": "Build a polished founder dinner outfit with accessories.", "accessories": "off"},
        ).json()
        on = client.post(
            "/api/v1/style-me",
            json={"prompt": "Build a polished founder dinner outfit.", "accessories": "on"},
        ).json()

    assert all(item["category"] != "accessory" for item in off["recommended_items"])
    assert any(item["category"] == "accessory" for item in on["recommended_items"])


def test_accessory_auto_skips_bags_unless_requested():
    with TestClient(app) as client:
        no_bag = client.post(
            "/api/v1/style-me",
            json={"prompt": "I need a complete gallery opening outfit with accessories."},
        ).json()
        with_bag = client.post(
            "/api/v1/style-me",
            json={"prompt": "Complete weekend outfit and include a weekender bag."},
        ).json()

    bag_words = ("bag", "tote", "backpack", "weekender", "satchel", "purse")
    accessories = [i for i in no_bag["recommended_items"] if i["category"] == "accessory"]
    assert accessories, "auto + 'with accessories' should add an accessory"
    assert not any(any(w in a["name"].lower() for w in bag_words) for a in accessories)
    # When the prompt explicitly asks for a bag, one should appear.
    assert any(
        i["category"] == "accessory" and any(w in i["name"].lower() for w in bag_words)
        for i in with_bag["recommended_items"]
    )
