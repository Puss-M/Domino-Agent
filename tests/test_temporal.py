from __future__ import annotations

from backend.app.config import get_settings
from backend.app.evaluation.dataset import load_events
from backend.app.evaluation.temporal import audit_point_in_time, load_point_in_time


def test_manifest_declares_the_benchmark_sources():
    manifest = load_point_in_time(settings=get_settings())
    ids = {source["id"] for source in manifest["sources"]}
    assert {"yahoo", "curated_events", "fomc", "brw"} <= ids
    yahoo = next(source for source in manifest["sources"] if source["id"] == "yahoo")
    assert yahoo["point_in_time"] == "no"
    assert yahoo["used_in_benchmark"] is True


def test_curated_audit_flags_revised_prices_and_labels():
    settings = get_settings()
    events = load_events(settings=settings, dataset="curated")
    audit = audit_point_in_time(events, dataset="curated", settings=settings)
    assert audit["n_events"] == 50
    assert audit["llm_in_metric_path"] is False
    assert audit["verdict"] == "not_point_in_time"
    assert "yahoo" in audit["revised_sources"]
    assert "curated_events" in audit["revised_sources"]
    assert "brw" not in audit["revised_sources"]
    assert all(check["passed"] for check in audit["checks"] if check["id"] == "no_llm_metric_path")


def test_surprise_benchmark_also_flags_the_ex_post_series():
    settings = get_settings()
    events = load_events(settings=settings, dataset="fomc_surprise")
    audit = audit_point_in_time(events, dataset="fomc_surprise", settings=settings)
    assert audit["n_events"] == 45
    assert "brw" in audit["revised_sources"]
    assert "curated_events" not in audit["revised_sources"]
