from __future__ import annotations

from backend.app.config import get_settings
from backend.app.datasources import MarketData
from backend.app.evaluation.cross_sectional import build_panel, evaluate_cross_sectional
from backend.app.evaluation.dataset import load_events
from backend.app.schemas import BacktestConfig

ASSETS = ["SPY", "QQQ", "TLT", "IEF", "UUP", "GLD", "XLE", "XLU", "EEM", "HYG", "^VIX", "FXI"]


def _data():
    settings = get_settings()
    market = MarketData(settings)
    prices = market.prices_wide("adj_close", ASSETS + ["SPY"]).dropna(how="all")
    events = load_events(settings=settings, dataset="curated")
    return events, prices


def test_panel_features_are_strictly_pre_event():
    events, prices = _data()
    panel, skipped = build_panel(events, prices, ASSETS, BacktestConfig(dataset="curated"))
    assert not panel.empty
    assert not skipped
    assert {"event_id", "event_day", "feature_end", "asset", "car_bps", "rank_pct"} <= set(panel.columns)
    assert (panel["feature_end"] < panel["event_day"]).all()
    assert panel.groupby("event_id")["asset"].nunique().min() >= 4


def test_cross_sectional_walk_forward_contract():
    events, prices = _data()
    result = evaluate_cross_sectional(
        events, prices, ASSETS, BacktestConfig(dataset="curated")
    )
    assert result["n_events"] == 50
    assert result["n_rows"] > 500
    assert result["n_folds"] == 5
    assert {"lightgbm", "ridge", "momentum", "random"} <= set(result["models"])
    for metrics in result["models"].values():
        if metrics.get("mean_rank_ic") is not None:
            assert -1.0 <= metrics["mean_rank_ic"] <= 1.0
        if metrics.get("gross_ls_ci"):
            low, high = metrics["gross_ls_ci"]
            assert low <= high
        assert set(metrics["net_ls_bps"]) == {"5", "10", "20"}
        if metrics.get("deflated_sharpe"):
            assert 0.0 <= metrics["deflated_sharpe"]["deflated_sharpe"] <= 1.0
    assert result["leakage_checks"]["feature_end_before_event"] is True
    assert "multiple_testing" in result
    assert "holm_gross_ls_p" in result["multiple_testing"]
