from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from backend.app.evaluation.backtest import BacktestEngine
from backend.app.evaluation.event_study import Outcome, cross_sectional_test
from backend.app.schemas import (
    BacktestConfig,
    Direction,
    EventType,
    LabeledEvent,
    SourceRef,
)

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


def test_kolar_pynnonen_counts_cross_correlation():
    """With a shared factor, the KP t-stat must be smaller than BMP."""
    rng = np.random.default_rng(3)
    days = pd.bdate_range("2020-01-01", periods=180)
    common = rng.normal(0.0, 0.01, len(days))
    prices = pd.DataFrame({"SPY": 100 * np.cumprod(1 + common)}, index=days)
    for asset in ("AAA", "BBB", "CCC"):
        prices[asset] = 100 * np.cumprod(1 + common + rng.normal(0.0, 0.001, len(days)))

    event = LabeledEvent(
        id="synthetic-1",
        headline="Synthetic event",
        published_at=datetime(2020, 1, 1) + (days[150] - days[0]),
        source=SourceRef(name="test"),
        event_type=EventType.MONETARY_POLICY,
        direction=Direction.TIGHTENING,
        confidence=1.0,
        gold_event_type=EventType.MONETARY_POLICY,
        gold_direction=Direction.TIGHTENING,
        session="during",
    )
    outcomes = {
        event.id: {
            asset: Outcome(
                event_id=event.id,
                asset=asset,
                event_day=days[150].date(),
                window_start=days[150].date(),
                window_end=days[151].date(),
                car=0.01,
                car_bps=100.0,
                raw_return=0.01,
                alpha=0.0,
                beta=0.0,
                sigma=0.01,
                t_stat=t_stat,
                direction="up",
            )
            for asset, t_stat in zip(("AAA", "BBB", "CCC"), (1.5, 0.8, -0.4))
        }
    }
    result = cross_sectional_test(
        outcomes, [event], prices, ["AAA", "BBB", "CCC"], BacktestConfig()
    )
    assert result["n_events"] == 1
    assert result["mean_rho_bar"] > 0.5
    assert result["mean_abs_kp_t"] < result["mean_abs_bmp_t"]
