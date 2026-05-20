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

    assert response.status_code == 200
    assert response.json()["catalog_items"] >= 100
    assert catalog.status_code == 200
    categories = [item["category"] for item in catalog.json()]
    assert "top" in categories
    assert "bottom" in categories
