"""Event-study math.

Protocol (deliberately standard, deliberately boring):
- market model estimated on [-120, -21] trading days relative to the event day;
- abnormal return AR_t = R_it - (alpha_i + beta_i * R_mt);
- cumulative abnormal return over [0, +5] trading days;
- the market asset (SPY) is evaluated on its raw return, because its market-
  model residual is zero by construction;
- events after the close or on a non-trading day are aligned to the next
  trading day, which is the first session that can price the news.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ..schemas import BacktestConfig, LabeledEvent

MARKET_ASSET = "SPY"


@dataclass
class Outcome:
    event_id: str
    asset: str
    event_day: date
    window_start: date
    window_end: date
    car: float
    car_bps: float
    raw_return: float
    alpha: float
    beta: float
    sigma: float
    t_stat: float
    direction: str

    def to_dict(self) -> dict:
        return {
            "event_day": self.event_day.isoformat(),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "car": round(self.car, 6),
            "car_bps": round(self.car_bps, 2),
            "raw_return": round(self.raw_return, 6),
            "alpha": round(self.alpha, 6),
            "beta": round(self.beta, 4),
            "sigma": round(self.sigma, 4),
            "t_stat": round(self.t_stat, 2),
            "direction": self.direction,
        }


def trading_days(prices: pd.DataFrame) -> list[pd.Timestamp]:
    return [pd.Timestamp(index).normalize() for index in prices.index]


def event_day_index(
    days: list[pd.Timestamp],
    event_date: date,
    session: str,
) -> int | None:
    target = pd.Timestamp(event_date).normalize()
    arr = pd.DatetimeIndex(days)
    if session in {"after_close", "non_trading"}:
        position = int(arr.searchsorted(target, side="right"))
    else:
        position = int(arr.searchsorted(target, side="left"))
    return position if 0 <= position < len(days) else None


def _direction(car: float, threshold_bps: float) -> str:
    if abs(car) * 10000 < threshold_bps:
        return "flat"
    return "up" if car > 0 else "down"


def compute_outcomes(
    events: list[LabeledEvent],
    prices: pd.DataFrame,
    assets: list[str],
    config: BacktestConfig | None = None,
) -> tuple[dict[str, dict[str, Outcome]], list[str]]:
    config = config or BacktestConfig()
    returns = prices.pct_change()
    days = trading_days(prices)
    outcomes: dict[str, dict[str, Outcome]] = {}
    skipped: list[str] = []

    for event in events:
        idx = event_day_index(days, event.published_at.date(), event.session)
        if idx is None:
            skipped.append(f"{event.id}: no trading day")
            continue
        est_idx = list(range(idx + config.estimation_start, idx + config.estimation_end + 1))
        win_idx = list(range(idx + config.window_start, idx + config.window_end + 1))
        if est_idx[0] < 0 or win_idx[-1] >= len(days):
            skipped.append(f"{event.id}: insufficient price window")
            continue
        event_outcomes: dict[str, Outcome] = {}
        for asset in assets:
            if asset not in returns.columns or MARKET_ASSET not in returns.columns:
                continue
            y_est = returns[asset].iloc[est_idx].dropna()
            x_est = returns[MARKET_ASSET].iloc[est_idx].dropna()
            joined = pd.concat([y_est, x_est], axis=1, keys=["asset", "market"]).dropna()
            if len(joined) < 60:
                continue
            market_var = float(joined["market"].var(ddof=1))
            if market_var <= 1e-12:
                continue
            beta = float(joined["asset"].cov(joined["market"]) / market_var)
            alpha = float(joined["asset"].mean() - beta * joined["market"].mean())
            residuals = joined["asset"] - (alpha + beta * joined["market"])
            sigma = float(residuals.std(ddof=2))

            y_win = returns[asset].iloc[win_idx].dropna()
            x_win = returns[MARKET_ASSET].iloc[win_idx].dropna()
            window = pd.concat([y_win, x_win], axis=1, keys=["asset", "market"]).dropna()
            if len(window) < (config.window_end - config.window_start + 1):
                continue
            if asset == MARKET_ASSET:
                abnormal = window["asset"]
                car = float((1 + window["asset"]).prod() - 1)
            else:
                abnormal = window["asset"] - (alpha + beta * window["market"])
                car = float(abnormal.sum())
            raw_return = float((1 + window["asset"]).prod() - 1)
            se = sigma * math.sqrt(len(abnormal)) if sigma > 0 else float("inf")
            t_stat = car / se if se > 0 else 0.0
            threshold = 100.0 if asset == "^VIX" else config.flat_threshold_bps
            event_outcomes[asset] = Outcome(
                event_id=event.id,
                asset=asset,
                event_day=days[idx].date(),
                window_start=days[win_idx[0]].date(),
                window_end=days[win_idx[-1]].date(),
                car=car,
                car_bps=car * 10000,
                raw_return=raw_return,
                alpha=alpha,
                beta=beta,
                sigma=sigma,
                t_stat=t_stat,
                direction=_direction(car, threshold),
            )
        outcomes[event.id] = event_outcomes
    return outcomes, skipped


def event_study_summary(outcomes: dict[str, dict[str, Outcome]], asset: str) -> dict:
    cars = [
        event[asset].car_bps
        for event in outcomes.values()
        if asset in event and event[asset].direction != "flat"
    ]
    if not cars:
        return {"asset": asset, "n": 0, "mean_car_bps": None, "t_stat": None}
    array = np.array(cars)
    mean = float(array.mean())
    se = float(array.std(ddof=1) / math.sqrt(len(array))) if len(array) > 1 else float("nan")
    return {
        "asset": asset,
        "n": len(array),
        "mean_car_bps": round(mean, 2),
        "t_stat": round(mean / se, 2) if se and not math.isnan(se) else None,
        "hit_rate_up": round(float((array > 0).mean()), 4),
    }
