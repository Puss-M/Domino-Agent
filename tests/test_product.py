from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app.api import create_app
from backend.app.config import get_settings
from backend.app.product import ProductStore


def _client(tmp_path):
    settings = replace(get_settings(), cache_dir=tmp_path)
    return TestClient(create_app(settings))


def test_product_store_watchlist_roundtrip(tmp_path):
    store = ProductStore(path=tmp_path / "product.db")
    assert "SPY" in store.list_watchlist()
    assets = store.add_watchlist("xle")
    assert "XLE" in assets
    assets = store.remove_watchlist("XLE")
    assert "XLE" not in assets


def test_calendar_and_digest_endpoints(tmp_path):
    client = _client(tmp_path)
    calendar = client.get("/api/calendar?days=120")
    assert calendar.status_code == 200
    payload = calendar.json()
    assert payload["n_events"] > 0
    event = payload["events"][0]

    digest = client.get("/api/digest?days=30&format=md")
    assert digest.status_code == 200
    assert "Macro Audit Digest" in digest.text
    assert event["title"] in digest.text

    html = client.get("/api/digest?days=30&format=html")
    assert html.status_code == 200
    assert "Macro Audit Digest" in html.text


def test_note_creation_html_pdf_and_review(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/api/notes",
        json={
            "headline": "Fed raises rates by 50 basis points",
            "summary": "The FOMC raises the target range by 50bp.",
            "published_at": "2022-06-15T18:00:00Z",
            "session": "during",
            "source_name": "test",
        },
    )
    assert created.status_code == 200
    note = created.json()
    note_id = note["id"]
    assert note["payload"]["event"]["event_type"] == "monetary_policy"

    listed = client.get("/api/notes").json()["notes"]
    assert any(item["id"] == note_id for item in listed)

    html = client.get(f"/api/notes/{note_id}/html")
    assert html.status_code == 200
    assert "Macro Event Audit" in html.text

    pdf = client.get(f"/api/notes/{note_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    reviewed = client.post(f"/api/notes/{note_id}/review")
    assert reviewed.status_code == 200
    review = reviewed.json()["review"]
    assert review["status"] in {"reviewed", "pending"}


def test_calendar_scenario_overrides_the_headline(tmp_path):
    client = _client(tmp_path)
    calendar = client.get("/api/calendar?days=400").json()
    fomc = next(event for event in calendar["events"] if event["event_type"] == "monetary_policy")
    created = client.post(
        "/api/notes",
        json={
            "event_id": fomc["id"],
            "headline": "Fed raises rates by 25 basis points",
            "summary": "Scenario: a 25bp hike at the next meeting.",
            "session": fomc["session"],
            "published_at": f"{fomc['date']}T00:00:00Z",
        },
    )
    assert created.status_code == 200
    note = created.json()
    assert note["event_id"] == fomc["id"]
    assert note["headline"] == "Fed raises rates by 25 basis points"
    assert note["payload"]["event"]["event_type"] == "monetary_policy"


def test_watchlist_api_and_product_page(tmp_path):
    client = _client(tmp_path)
    assert client.get("/product").status_code == 200
    added = client.post("/api/watchlist", json={"asset": "gld"})
    assert added.status_code == 200
    assert "GLD" in added.json()["assets"]
    removed = client.delete("/api/watchlist/GLD")
    assert "GLD" not in removed.json()["assets"]
