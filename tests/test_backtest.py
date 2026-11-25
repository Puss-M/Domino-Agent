from __future__ import annotations

from backend.app.evaluation.backtest import BacktestEngine
from backend.app.schemas import BacktestConfig

SUBSET = [
    "fomc-2022-03-16",
    "fomc-2022-06-15",
    "cpi-2022-06-10",
    "cpi-2022-11-10",
    "trade-2018-03-22",
    "opec-2022-10-05",
    "geo-2022-02-24",
    "bank-2023-03-12",
    "china-2024-09-24",
    "fomc-2024-09-18",
]


def test_walk_forward_backtest_contract():
    config = BacktestConfig(include_events=SUBSET, window_end=1, bootstrap_samples=30)
    result = BacktestEngine(config=config).run(config)
    assert result.n_events == len(SUBSET)
    assert result.n_outcome_observations > 0
    assert len(result.metrics) >= 8
    assert result.extraction.n == len(SUBSET)
    assert result.extraction.joint_accuracy == 1.0
    assert result.events
    for metric in result.metrics:
        if metric.accuracy is not None:
            assert 0.0 <= metric.accuracy <= 1.0
        if metric.brier is not None:
            assert 0.0 <= metric.brier <= 1.0
    assert any("Stack weights" in note for note in result.notes)


def test_fomc_stress_test_contract():
    config = BacktestConfig(dataset="fomc", window_end=1, bootstrap_samples=30)
    result = BacktestEngine(config=config).run(config)
    assert result.n_events == 58
    # Templated FOMC headlines are excluded from the extraction metric.
    assert result.extraction.n == 0
    assert result.comparisons
    names = {metric.model for metric in result.metrics}
    assert "stacked_calibrated_test" in names
    assert any("Dataset: fomc" in note for note in result.notes)


def test_event_detail_contains_realized_outcomes():
    config = BacktestConfig(include_events=SUBSET[:4], window_end=1, bootstrap_samples=20)
    result = BacktestEngine(config=config).run(config)
    event = result.events[0]
    assert event.realized
    for asset, outcome in event.realized.items():
        assert "car_bps" in outcome
        assert outcome["direction"] in {"up", "down", "flat"}
    for asset, prediction in event.predictions.items():
        assert "mechanism" in prediction
        assert "analog" in prediction
        assert "stacked" in prediction
