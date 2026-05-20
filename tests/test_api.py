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
    assert "accessory" in intent_detail
    assert any(item["category"] == "accessory" for item in data["recommended_items"])
    assert any(term in data["stylist_note"].lower() for term in ["tech", "nerdy", "suave"])
