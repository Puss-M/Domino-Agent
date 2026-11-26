"""Event-study evaluation and walk-forward backtesting."""

from .analog import AnalogModel, AnalogPrediction, direction_bucket
from .backtest import BacktestEngine
from .cross_sectional import build_panel, evaluate_cross_sectional
from .dataset import DatasetError, load_events, news_item, split_by_date
from .event_study import (
    Outcome,
    compute_outcomes,
    cross_sectional_test,
    event_day_index,
    event_study_summary,
)
from .metrics import (
    accuracy,
    apply_platt,
    auc,
    bootstrap_ci,
    brier,
    calibration_bins,
    expected_calibration_error,
    fit_platt,
    log_loss,
    summarize,
)
from .temporal import audit_point_in_time, load_point_in_time

__all__ = [
    "AnalogModel",
    "AnalogPrediction",
    "BacktestEngine",
    "DatasetError",
    "Outcome",
    "accuracy",
    "apply_platt",
    "auc",
    "audit_point_in_time",
    "bootstrap_ci",
    "brier",
    "build_panel",
    "calibration_bins",
    "compute_outcomes",
    "cross_sectional_test",
    "direction_bucket",
    "event_day_index",
    "event_study_summary",
    "evaluate_cross_sectional",
    "expected_calibration_error",
    "fit_platt",
    "load_events",
    "load_point_in_time",
    "log_loss",
    "news_item",
    "split_by_date",
    "summarize",
]
