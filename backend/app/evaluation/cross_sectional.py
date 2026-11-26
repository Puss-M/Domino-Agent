"""E13: cross-sectional, cost-aware evaluation.

The unit of prediction is an (event, asset) row. The target is the within-event
percentile rank of the realised CAR[0,+1], not an independent up/down label.
This follows the cross-sectional protocol used by Qlib and PaCMoE, and is the
main lesson from the 2026 accuracy sweep: rank the cross-section, use a strong
tabular baseline, and evaluate net of costs.

The protocol is deliberately conservative:

- features use prices strictly before the event day (``returns[:idx]``);
- folds are expanding-window by event date;
- LightGBM is compared with momentum and ridge;
- long-short returns are reported gross and net of 5/10/20bp one-way costs;
- a paired event bootstrap tests LightGBM vs momentum.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from ..schemas import BacktestConfig, Direction, EventType, LabeledEvent
from .event_study import MARKET_ASSET, compute_outcomes, event_day_index, trading_days

_EVENT_TYPES = [item.value for item in EventType]
_DIRECTIONS = [item.value for item in Direction]
_UNITS = ["bps", "pp", "pct", "usd_bn", "mbpd", "count", "qualitative"]


def _safe_return(series: pd.Series, window: int) -> float:
    values = series.dropna().iloc[-window:]
    if len(values) < 2:
        return 0.0
    return float((1 + values).prod() - 1)


def _safe_vol(series: pd.Series, window: int) -> float:
    values = series.dropna().iloc[-window:]
    if len(values) < 3:
        return 0.0
    return float(values.std(ddof=1) * math.sqrt(252))


def _safe_corr(left: pd.Series, right: pd.Series, window: int) -> float:
    joined = pd.concat([left, right], axis=1, keys=["left", "right"]).dropna().iloc[-window:]
    if len(joined) < 10:
        return 0.0
    value = joined["left"].corr(joined["right"])
    return float(value) if not math.isnan(value) else 0.0


def _event_features(event: LabeledEvent) -> dict[str, float]:
    sentiment = event.text_sentiment or {}
    magnitude = event.magnitude
    surprise = event.surprise
    features: dict[str, float] = {
        "magnitude_value": float(magnitude.value) if magnitude else 0.0,
        "surprise_value": float(surprise.value) if surprise else 0.0,
        "surprise_sign": (
            -1.0
            if surprise and surprise.sign == "negative"
            else 1.0
            if surprise and surprise.sign == "positive"
            else 0.0
        ),
        "confidence": float(event.confidence),
        "sentiment_polarity": float(sentiment.get("polarity", 0.0)),
        "sentiment_uncertainty": float(sentiment.get("uncertainty", 0.0)),
        "sentiment_hawkish": float(sentiment.get("hawkish", 0.0)),
        "sentiment_dovish": float(sentiment.get("dovish", 0.0)),
        "sentiment_risk_off": float(sentiment.get("risk_off", 0.0)),
        "sentiment_risk_on": float(sentiment.get("risk_on", 0.0)),
    }
    for value in _EVENT_TYPES:
        features[f"type_{value}"] = 1.0 if event.event_type.value == value else 0.0
    for value in _DIRECTIONS:
        features[f"dir_{value}"] = 1.0 if event.direction.value == value else 0.0
    unit = magnitude.unit if magnitude else "qualitative"
    for value in _UNITS:
        features[f"unit_{value}"] = 1.0 if unit == value else 0.0
    features["session_after_close"] = 1.0 if event.session == "after_close" else 0.0
    features["session_non_trading"] = 1.0 if event.session == "non_trading" else 0.0
    features["session_before_open"] = 1.0 if event.session == "before_open" else 0.0
    features["session_during"] = 1.0 if event.session == "during" else 0.0
    return features


def build_panel(
    events: list[LabeledEvent],
    prices: pd.DataFrame,
    assets: list[str],
    config: BacktestConfig | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Build an (event, asset) panel with strictly pre-event features."""
    config = config or BacktestConfig()
    outcomes, skipped = compute_outcomes(events, prices, assets, config)
    returns = prices.pct_change()
    days = trading_days(prices)
    rows: list[dict[str, Any]] = []

    for event in sorted(events, key=lambda item: item.published_at):
        event_outcomes = outcomes.get(event.id, {})
        if len(event_outcomes) < 4:
            skipped.append(f"{event.id}: fewer than 4 priced assets")
            continue
        idx = event_day_index(days, event.published_at.date(), event.session)
        if idx is None or idx < 60:
            skipped.append(f"{event.id}: insufficient pre-event history")
            continue
        prior = returns.iloc[max(0, idx - 120) : idx]
        prior_prices = prices.iloc[max(0, idx - 120) : idx]
        if len(prior) < 60 or MARKET_ASSET not in prior.columns:
            skipped.append(f"{event.id}: insufficient pre-event returns")
            continue
        feature_end = days[idx - 1].date()
        event_features = _event_features(event)
        event_rows: list[dict[str, Any]] = []
        for asset, outcome in event_outcomes.items():
            if asset not in prior.columns:
                continue
            series = prior[asset]
            if series.dropna().shape[0] < 60:
                continue
            beta_window = pd.concat(
                [series, prior[MARKET_ASSET]], axis=1, keys=["asset", "market"]
            ).dropna().iloc[-60:]
            market_var = float(beta_window["market"].var(ddof=1)) if len(beta_window) > 2 else 0.0
            beta = (
                float(beta_window["asset"].cov(beta_window["market"]) / market_var)
                if market_var > 1e-12
                else 0.0
            )
            price_series = prior_prices[asset].dropna()
            distance_high = 0.0
            if len(price_series) >= 20:
                last = float(price_series.iloc[-1])
                high = float(price_series.iloc[-60:].max())
                distance_high = last / high - 1 if high > 0 else 0.0
            row = {
                "event_id": event.id,
                "event_day": days[idx].date(),
                "feature_end": feature_end,
                "asset": asset,
                "car_bps": float(outcome.car_bps),
                "trailing_20": _safe_return(series, 20),
                "trailing_60": _safe_return(series, 60),
                "vol_20": _safe_vol(series, 20),
                "vol_60": _safe_vol(series, 60),
                "beta_60": beta,
                "corr_spy": _safe_corr(series, prior[MARKET_ASSET], 60),
                "corr_tlt": _safe_corr(series, prior["TLT"], 60) if "TLT" in prior else 0.0,
                "corr_uup": _safe_corr(series, prior["UUP"], 60) if "UUP" in prior else 0.0,
                "dist_high_60": distance_high,
                **event_features,
            }
            if "^VIX" in prior.columns:
                vix = prior["^VIX"].dropna()
                row["vix_level"] = float(vix.iloc[-1]) if len(vix) else 0.0
                row["vix_change_5d"] = _safe_return(vix / 100.0, 5) if len(vix) else 0.0
            else:
                row["vix_level"] = 0.0
                row["vix_change_5d"] = 0.0
            event_rows.append(row)
        if len(event_rows) < 4:
            skipped.append(f"{event.id}: fewer than 4 usable feature rows")
            continue
        frame = pd.DataFrame(event_rows)
        frame["rank_pct"] = frame["car_bps"].rank(pct=True, method="average")
        frame["cs_rank_momentum"] = frame["trailing_20"].rank(pct=True, method="average")
        frame["cs_rank_vol"] = frame["vol_20"].rank(pct=True, method="average")
        frame["cs_rank_beta"] = frame["beta_60"].rank(pct=True, method="average")
        frame["cs_rank_corr_spy"] = frame["corr_spy"].rank(pct=True, method="average")
        rows.extend(frame.to_dict("records"))
    return pd.DataFrame(rows), skipped


def _feature_columns(panel: pd.DataFrame) -> list[str]:
    excluded = {
        "event_id",
        "event_day",
        "feature_end",
        "asset",
        "car_bps",
        "rank_pct",
    }
    return [
        column
        for column in panel.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(panel[column])
    ]


def _rank_ic(frame: pd.DataFrame) -> float | None:
    if len(frame) < 4 or frame["score"].nunique() < 2 or frame["car_bps"].nunique() < 2:
        return None
    value = frame["score"].corr(frame["car_bps"], method="spearman")
    return float(value) if not math.isnan(value) else None


def _event_metrics(frame: pd.DataFrame, k: int = 3) -> dict[str, Any] | None:
    ranked_pred = frame.sort_values("score", ascending=False)
    ranked_real = frame.sort_values("car_bps", ascending=False)
    if len(ranked_pred) < 4:
        return None
    k = min(k, max(2, len(frame) // 3))
    pred_top = set(ranked_pred["asset"].head(k))
    real_top = set(ranked_real["asset"].head(k))
    top = float(ranked_pred.head(k)["car_bps"].mean())
    bottom = float(ranked_pred.tail(k)["car_bps"].mean())
    return {
        "rank_ic": _rank_ic(frame),
        "top1_hit": 1.0 if ranked_pred["asset"].iloc[0] == ranked_real["asset"].iloc[0] else 0.0,
        "top3_overlap": len(pred_top & real_top) / k,
        "gross_ls_bps": top - bottom,
        "n_assets": len(frame),
    }


def _bootstrap_mean(values: np.ndarray, samples: int = 500, seed: int = 17) -> dict:
    if len(values) < 5:
        return {"mean": None, "ci": None, "p_value": None}
    rng = np.random.default_rng(seed)
    draws = [float(values[rng.integers(0, len(values), len(values))].mean()) for _ in range(samples)]
    draws.sort()
    return {
        "mean": round(float(values.mean()), 2),
        "ci": (round(draws[int(0.025 * len(draws))], 2), round(draws[int(0.975 * len(draws)) - 1], 2)),
        "p_value": round(float(np.mean(np.asarray(draws) <= 0)), 4),
    }


def _pair_bootstrap(values: list[float], samples: int = 500, seed: int = 13) -> dict:
    if len(values) < 5:
        return {"delta": None, "ci": None, "p_value": None, "n": len(values)}
    rng = np.random.default_rng(seed)
    array = np.asarray(values, dtype=float)
    deltas = [
        float(array[rng.integers(0, len(array), len(array))].mean()) for _ in range(samples)
    ]
    deltas.sort()
    return {
        "delta": round(float(array.mean()), 2),
        "ci": (round(deltas[int(0.025 * len(deltas))], 2), round(deltas[int(0.975 * len(deltas)) - 1], 2)),
        "p_value": round(float(np.mean(np.asarray(deltas) <= 0)), 4),
        "n": len(values),
    }


def _fit_ridge(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    alpha: float = 1.0,
) -> np.ndarray:
    mean = train_x.mean(axis=0)
    std = train_x.std(axis=0)
    std[std < 1e-9] = 1.0
    x_train = (train_x - mean) / std
    x_test = (test_x - mean) / std
    x_train = np.column_stack([np.ones(len(x_train)), x_train])
    x_test = np.column_stack([np.ones(len(x_test)), x_test])
    penalty = np.eye(x_train.shape[1]) * alpha
    penalty[0, 0] = 0.0
    weights = np.linalg.solve(x_train.T @ x_train + penalty, x_train.T @ train_y)
    return x_test @ weights


def walk_forward(panel: pd.DataFrame, min_train_events: int = 20, n_folds: int = 5) -> dict:
    if panel.empty:
        return {"n_events": 0, "models": {}, "folds": []}
    feature_columns = _feature_columns(panel)
    event_days = sorted(panel["event_day"].unique())
    if len(event_days) <= min_train_events + 1:
        return {"n_events": len(event_days), "models": {}, "folds": [], "notes": ["not enough events for walk-forward"]}
    test_size = max(2, (len(event_days) - min_train_events) // n_folds)
    folds = []
    model_event_metrics: dict[str, list[dict]] = defaultdict(list)
    importance: dict[str, float] = defaultdict(float)

    try:
        import lightgbm as lgb
    except ImportError:  # pragma: no cover - requirements include lightgbm
        lgb = None

    for fold_index in range(n_folds):
        start = min_train_events + fold_index * test_size
        end = len(event_days) if fold_index == n_folds - 1 else min(start + test_size, len(event_days))
        if start >= len(event_days) or end <= start:
            break
        train_days = event_days[:start]
        test_days = event_days[start:end]
        train = panel[panel["event_day"].isin(train_days)].copy()
        test = panel[panel["event_day"].isin(test_days)].copy()
        if train.empty or test.empty:
            continue
        train_x = train[feature_columns].fillna(0.0).to_numpy(dtype=float)
        test_x = test[feature_columns].fillna(0.0).to_numpy(dtype=float)
        train_y = train["rank_pct"].to_numpy(dtype=float)

        scores: dict[str, np.ndarray] = {}
        if lgb is not None:
            train_data = lgb.Dataset(train_x, label=train_y)
            params = {
                "objective": "regression",
                "metric": "l2",
                "boosting_type": "gbdt",
                "num_leaves": 7,
                "learning_rate": 0.05,
                "min_data_in_leaf": 8,
                "feature_fraction": 0.85,
                "bagging_fraction": 0.85,
                "bagging_freq": 1,
                "lambda_l2": 1.0,
                "verbose": -1,
                "seed": 42 + fold_index,
                "num_threads": 1,
            }
            booster = lgb.train(params, train_data, num_boost_round=120)
            scores["lightgbm"] = booster.predict(test_x)
            for name, value in zip(feature_columns, booster.feature_importance(importance_type="split")):
                importance[name] += float(value)
        scores["ridge"] = _fit_ridge(train_x, train_y, test_x)
        scores["momentum"] = test["trailing_20"].to_numpy(dtype=float)
        rng = np.random.default_rng(100 + fold_index)
        scores["random"] = rng.random(len(test))

        fold_metrics: dict[str, Any] = {
            "fold": fold_index,
            "train_events": len(train_days),
            "test_events": len(test_days),
            "test_rows": len(test),
        }
        for name, score in scores.items():
            scored = test.copy()
            scored["score"] = score
            per_event = []
            for event_day, frame in scored.groupby("event_day"):
                metrics = _event_metrics(frame)
                if metrics:
                    metrics["event_day"] = str(event_day)
                    per_event.append(metrics)
            model_event_metrics[name].extend(per_event)
            fold_metrics[name] = _aggregate(per_event)
        folds.append(fold_metrics)

    models = {name: _aggregate(rows) for name, rows in model_event_metrics.items()}
    # Paired difference per event for LightGBM vs momentum.
    lgb_by_day = {row["event_day"]: row for row in model_event_metrics.get("lightgbm", [])}
    mom_by_day = {row["event_day"]: row for row in model_event_metrics.get("momentum", [])}
    paired = [
        lgb_by_day[day]["gross_ls_bps"] - mom_by_day[day]["gross_ls_bps"]
        for day in sorted(set(lgb_by_day) & set(mom_by_day))
    ]
    top_importance = sorted(importance.items(), key=lambda item: item[1], reverse=True)[:10]
    return {
        "n_events": len(event_days),
        "n_rows": len(panel),
        "n_folds": len(folds),
        "feature_columns": feature_columns,
        "models": models,
        "comparison": {"lightgbm_minus_momentum_gross_ls_bps": _pair_bootstrap(paired)},
        "feature_importance": [{"feature": name, "importance": round(value, 2)} for name, value in top_importance],
        "folds": folds,
        "leakage_checks": {
            "feature_end_before_event": bool(
                (pd.to_datetime(panel["feature_end"]) < pd.to_datetime(panel["event_day"])).all()
            ),
            "max_feature_end": str(max(panel["feature_end"])),
            "min_event_day": str(min(panel["event_day"])),
        },
    }


def _aggregate(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"n_events": 0}
    ics = [row["rank_ic"] for row in rows if row["rank_ic"] is not None]
    ls = np.asarray([row["gross_ls_bps"] for row in rows], dtype=float)
    mean_ls = float(ls.mean())
    std_ls = float(ls.std(ddof=1)) if len(ls) > 1 else float("nan")
    ls_summary = _bootstrap_mean(ls)
    return {
        "n_events": len(rows),
        "mean_rank_ic": round(float(np.mean(ics)), 4) if ics else None,
        "rank_ic_ir": round(float(np.mean(ics) / np.std(ics) * math.sqrt(len(ics))), 3)
        if len(ics) > 1 and np.std(ics) > 1e-12
        else None,
        "top1_hit": round(float(np.mean([row["top1_hit"] for row in rows])), 4),
        "top3_overlap": round(float(np.mean([row["top3_overlap"] for row in rows])), 4),
        "gross_ls_bps": round(mean_ls, 2),
        "gross_ls_ci": ls_summary["ci"],
        "gross_ls_p_value": ls_summary["p_value"],
        "gross_ls_std_bps": round(std_ls, 2) if not math.isnan(std_ls) else None,
        "net_ls_bps": {
            str(cost): round(mean_ls - 2 * cost, 2) for cost in (5, 10, 20)
        },
    }


def evaluate_cross_sectional(
    events: list[LabeledEvent],
    prices: pd.DataFrame,
    assets: list[str],
    config: BacktestConfig | None = None,
    min_train_events: int = 20,
    n_folds: int = 5,
) -> dict:
    config = config or BacktestConfig()
    panel, skipped = build_panel(events, prices, assets, config)
    result = walk_forward(panel, min_train_events=min_train_events, n_folds=n_folds)
    result.update(
        {
            "dataset": config.dataset,
            "target": "within-event percentile rank of CAR[0,+1]",
            "cost_model": "gross long-short exposure 1; net = gross - 2 * one-way bps",
            "skipped": skipped[:20],
            "n_skipped": len(skipped),
            "notes": [
                "Features use returns strictly before the event day; feature_end < event_day is asserted.",
                "Expanding-window folds are by event date; no event is in both train and test.",
                "LightGBM is compared with momentum, ridge and random; a paired event bootstrap tests LightGBM vs momentum.",
                "The panel is small; treat the result as a protocol demonstration, not an alpha claim.",
            ],
        }
    )
    return result
