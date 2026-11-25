"""Event-study evaluation and walk-forward backtesting."""

from .analog import AnalogModel, AnalogPrediction, direction_bucket
from .backtest import BacktestEngine
from .dataset import DatasetError, load_events, news_item, split_by_date
from .event_study import Outcome, compute_outcomes, event_day_index, event_study_summary
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

__all__ = [
    "AnalogModel",
    "AnalogPrediction",
    "BacktestEngine",
    "DatasetError",
    "Outcome",
    "accuracy",
    "apply_platt",
    "auc",
    "bootstrap_ci",
    "brier",
    "calibration_bins",
    "compute_outcomes",
    "direction_bucket",
    "event_day_index",
    "event_study_summary",
    "expected_calibration_error",
    "fit_platt",
    "load_events",
    "log_loss",
    "news_item",
    "split_by_date",
    "summarize",
]
