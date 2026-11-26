from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api import create_app
from backend.app.config import get_settings


def _client() -> TestClient:
    return TestClient(create_app(get_settings()))


def test_health():
    response = _client().get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["n_events"] == 50
    assert payload["n_mechanisms"] >= 15


def test_analyze_returns_graph_and_memo():
    response = _client().post(
        "/api/analyze",
        json={"headline": "Fed raises rates by 50 basis points", "source_name": "test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event"]["event_type"] == "monetary_policy"
    assert payload["event"]["direction"] == "tightening"
    assert payload["graph"]["nodes"]
    assert payload["graph"]["edges"]
    assert payload["predictions"]
    assert payload["memo"]["summary"]
    assert payload["audit"]["passed"] is True
    assert payload["symbolic"]["acyclic"] is True
    assert payload["symbolic"]["proofs"]
    assert payload["symbolic"]["policy_results"]
    assert payload["symbolic"]["ledger_hash"]


def test_analyze_rejects_empty_headline():
    response = _client().post("/api/analyze", json={"headline": ""})
    assert response.status_code == 422


def test_ontology_endpoint():
    response = _client().get("/api/ontology.ttl")
    assert response.status_code == 200
    assert "domino:Mechanism" in response.text
    assert "MON_TIGHTEN" in response.text


def test_mechanisms_and_events_catalogs():
    client = _client()
    mechanisms = client.get("/api/mechanisms")
    events = client.get("/api/events")
    sources = client.get("/api/data-sources")
    assert mechanisms.status_code == 200
    assert len(mechanisms.json()) >= 15
    assert events.status_code == 200
    assert len(events.json()) == 50
    assert sources.status_code == 200
    assert len(sources.json()) == 8


def test_events_endpoint_supports_datasets():
    client = _client()
    curated = client.get("/api/events").json()
    fomc = client.get("/api/events?dataset=fomc").json()
    fomc_surprise = client.get("/api/events?dataset=fomc_surprise").json()
    extended = client.get("/api/events?dataset=extended").json()
    assert len(curated) == 50
    assert len(fomc) == 58
    assert len(fomc_surprise) == 45
    assert len(extended) == 92


def test_market_snapshot():
    response = _client().get("/api/market/SPY")
    assert response.status_code == 200
    assert response.json()["adj_close"] > 0
    assert _client().get("/api/market/NOPE").status_code == 404


def test_event_study_endpoint():
    response = _client().get("/api/event-study?window_end=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_end"] == 1
    assert payload["dataset"] == "curated"
    assert payload["n_events"] > 0
    assert len(payload["summary"]) == 12
    cross_sectional = payload["cross_sectional"]
    assert cross_sectional["n_events"] > 0
    assert 0.0 <= cross_sectional["mean_rho_bar"] < 1.0
    assert cross_sectional["mean_abs_kp_t"] <= cross_sectional["mean_abs_bmp_t"]


def test_point_in_time_endpoint():
    response = _client().get("/api/point-in-time?dataset=curated")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"] == "curated"
    assert payload["n_events"] == 50
    assert payload["llm_in_metric_path"] is False
    assert payload["verdict"] == "not_point_in_time"
    assert "yahoo" in payload["revised_sources"]


def test_cross_sectional_endpoint():
    response = _client().get("/api/cross-sectional?dataset=curated")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"] == "curated"
    assert payload["n_events"] == 50
    assert payload["n_folds"] == 5
    assert "lightgbm" in payload["models"]
    assert payload["leakage_checks"]["feature_end_before_event"] is True


def test_backtest_endpoint_small_subset():
    client = _client()
    payload = {
        "include_events": [
            "fomc-2022-03-16",
            "fomc-2022-05-04",
            "cpi-2022-06-10",
            "cpi-2022-11-10",
            "fomc-2024-09-18",
            "fomc-2024-12-18",
        ],
        "window_end": 1,
        "bootstrap_samples": 30,
    }
    response = client.post("/api/backtest", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["n_events"] == 6
    assert result["extraction"]["joint_accuracy"] == 1.0
    names = {metric["model"] for metric in result["metrics"]}
    assert "stacked_calibrated_test" in names
    assert result["calibration"]
