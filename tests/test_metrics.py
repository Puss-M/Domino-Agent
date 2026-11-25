from __future__ import annotations

import math

import pytest

from backend.app.evaluation.metrics import (
    accuracy,
    paired_bootstrap_difference,
    apply_platt,
    auc,
    brier,
    calibration_bins,
    expected_calibration_error,
    fit_platt,
    log_loss,
    summarize,
)


def _rows():
    return [
        {"event_id": "e1", "asset": "SPY", "y": 1, "p_up": 0.8, "car_bps": 100},
        {"event_id": "e1", "asset": "TLT", "y": 0, "p_up": 0.2, "car_bps": -50},
        {"event_id": "e2", "asset": "SPY", "y": 0, "p_up": 0.3, "car_bps": -20},
        {"event_id": "e2", "asset": "TLT", "y": 1, "p_up": 0.7, "car_bps": 30},
    ]


def test_accuracy_and_brier():
    rows = _rows()
    assert accuracy(rows) == 1.0
    assert brier(rows) == pytest.approx((0.04 + 0.04 + 0.09 + 0.09) / 4)


def test_log_loss_is_finite():
    value = log_loss(_rows())
    assert value is not None
    assert math.isfinite(value)


def test_auc_perfect_ranking():
    assert auc(_rows()) == 1.0


def test_auc_handles_ties():
    rows = [
        {"event_id": "e1", "y": 1, "p_up": 0.5},
        {"event_id": "e2", "y": 0, "p_up": 0.5},
    ]
    assert auc(rows) == 0.5


def test_ece_is_zero_for_perfectly_calibrated_extremes():
    rows = [
        {"event_id": "e1", "y": 1, "p_up": 1.0},
        {"event_id": "e2", "y": 0, "p_up": 0.0},
    ]
    assert expected_calibration_error(rows) == pytest.approx(0.0, abs=1e-9)


def test_calibration_bins_equal_and_quantile():
    rows = _rows() * 10
    equal = calibration_bins(rows, bins=4, strategy="equal")
    quantile = calibration_bins(rows, bins=4, strategy="quantile")
    assert equal
    assert quantile
    assert all(0 <= bin["observed_frequency"] <= 1 for bin in quantile)


def test_platt_output_is_bounded():
    rows = [
        {"event_id": f"e{index}", "y": index % 2, "p_up": 0.2 + 0.6 * (index % 5) / 4}
        for index in range(80)
    ]
    params = fit_platt(rows)
    calibrated = apply_platt(0.7, params)
    assert 0.0 <= calibrated <= 1.0


def test_summarize_reports_coverage_and_ci():
    rows = _rows()
    summary = summarize("test", rows, total_candidates=4, bootstrap_samples=20)
    assert summary["coverage"] == 1.0
    assert summary["accuracy"] == 1.0
    assert summary["n"] == 4
    assert summary["brier_ci"] is None  # too few clusters for a stable interval


def test_paired_bootstrap_difference_detects_better_model():
    # Model A predicts perfectly; model B is anti-correlated, on 12 events.
    rows_a, rows_b = [], []
    for index in range(24):
        y = index % 2
        rows_a.append({"event_id": f"e{index // 2}", "asset": "SPY", "y": y, "p_up": 0.9 if y else 0.1})
        rows_b.append({"event_id": f"e{index // 2}", "asset": "SPY", "y": y, "p_up": 0.1 if y else 0.9})
    result = paired_bootstrap_difference(rows_a, rows_b, samples=200)
    assert result["delta_brier"] < 0
    assert result["ci"][1] < 0
    assert result["p_value"] == 0.0
    assert result["n_pairs"] == 12


def test_paired_bootstrap_difference_needs_enough_pairs():
    rows = [{"event_id": "e1", "asset": "SPY", "y": 1, "p_up": 0.8}]
    result = paired_bootstrap_difference(rows, rows, samples=10)
    assert result["delta_brier"] is None
    assert result["n_pairs"] == 1
