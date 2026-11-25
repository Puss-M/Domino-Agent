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
                # The market-model residual for SPY is zero by construction, so
                # its estimation sigma cannot be used for a t-statistic. Use the
                # raw return volatility over the event window instead. ddof=1
                # keeps a two-day window from degenerating to a zero sigma.
                sigma = float(abnormal.std(ddof=1)) if len(abnormal) > 1 else sigma
            else:
                abnormal = window["asset"] - (alpha + beta * window["market"])
                car = float(abnormal.sum())
            # A near-perfect fit produces a zero residual variance and an
            # unbounded t-statistic. Floor the daily sigma at 1bp.
            sigma = max(sigma, 1e-6)
            raw_return = float((1 + window["asset"]).prod() - 1)
            se = sigma * math.sqrt(len(abnormal))
            t_car = float(abnormal.sum())
            t_stat = t_car / se if se > 0 else 0.0
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

    # Events that share a calendar day share a market-wide shock. Collapse them
    # to one observation per day before computing the standard error; this is
    # a cluster-robust mean test, not a claim that the events are independent.
    by_day: dict[date, list[float]] = {}
    for event in outcomes.values():
        if asset not in event or event[asset].direction == "flat":
            continue
        by_day.setdefault(event[asset].event_day, []).append(event[asset].car_bps)
    day_means = np.array([np.mean(values) for values in by_day.values()])
    cluster_t = None
    if len(day_means) > 1:
        cluster_se = float(day_means.std(ddof=1) / math.sqrt(len(day_means)))
        if cluster_se > 0:
            cluster_t = round(mean / cluster_se, 2)

    return {
        "asset": asset,
        "n": len(array),
        "n_event_days": len(day_means),
        "mean_car_bps": round(mean, 2),
        "t_stat": round(mean / se, 2) if se and not math.isnan(se) else None,
        "cluster_t": cluster_t,
        "hit_rate_up": round(float((array > 0).mean()), 4),
    }


_T_CRIT_975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _t_critical(df: int) -> float:
    """Two-sided 5% critical value for a t distribution with ``df`` degrees."""
    if df >= 30:
        return 1.96
    return _T_CRIT_975.get(df, 1.96)


def _average_pairwise_correlation(frame: pd.DataFrame) -> float | None:
    """Average off-diagonal correlation, clipped to the KP domain [0, 0.99].

    Kolari-Pynnonen assume non-negative cross-sectional correlation. A negative
    sample average would shrink the variance and make the test anti-conservative,
    so it is floored at zero. Correlations above 0.99 are capped to keep the
    variance inflation finite.
    """
    if frame.shape[1] < 2:
        return None
    corr = frame.corr(min_periods=60)
    values = []
    columns = list(corr.columns)
    for i, left in enumerate(columns):
        for right in columns[i + 1 :]:
            value = corr.loc[left, right]
            if not math.isnan(value):
                values.append(float(value))
    if not values:
        return None
    return float(np.clip(np.mean(values), 0.0, 0.99))


def cross_sectional_test(
    outcomes: dict[str, dict[str, Outcome]],
    events: list,
    prices: pd.DataFrame,
    assets: list[str],
    config: BacktestConfig | None = None,
) -> dict:
    """Kolari-Pynnonen (2010) adjustment of the BMP standardized CAR test.

    The event-study cross-section is the set of assets that price the same
    macro event. Their abnormal returns are correlated (all equities load on
    the same shock), so the naive BMP t-statistic overstates significance.
    For each event:

        BMP_t = mean(CSAR_i) / (sd(CSAR_i) / sqrt(N))
        KP_t  = BMP_t / sqrt(1 + (N - 1) * rho_bar)

    where CSAR_i is the standardized CAR from the market model and rho_bar is
    the average pairwise correlation of estimation-window residuals. CSAR uses
    the estimation-window residual sigma without the BMP forecast-error
    inflation; BMP and KP share that input, so their comparison is unaffected.

    The function reports the per-event distribution and, separately, an
    equal-weighted pooled test. The pooled statistic is descriptive: the
    benchmark mixes tightening and easing events, so averaging signed CARs can
    cancel genuine effects.
    """
    config = config or BacktestConfig()
    returns = prices.pct_change()
    days = trading_days(prices)
    by_id = {event.id: event for event in events}
    rows: list[dict] = []

    for event_id, event_outcomes in outcomes.items():
        event = by_id.get(event_id)
        if event is None:
            continue
        idx = event_day_index(days, event.published_at.date(), event.session)
        if idx is None:
            continue
        est_idx = list(range(idx + config.estimation_start, idx + config.estimation_end + 1))
        if est_idx[0] < 0:
            continue
        # SPY is excluded: its market-model residual is zero by construction, so
        # its standardized CAR is not comparable to the other assets'.
        present = [
            asset
            for asset in assets
            if asset in event_outcomes
            and asset != MARKET_ASSET
            and math.isfinite(event_outcomes[asset].t_stat)
        ]
        if len(present) < 3 or MARKET_ASSET not in returns.columns:
            continue
        residuals: dict[str, pd.Series] = {}
        for asset in present:
            if asset not in returns.columns:
                continue
            outcome = event_outcomes[asset]
            y = returns[asset].iloc[est_idx]
            x = returns[MARKET_ASSET].iloc[est_idx]
            residuals[asset] = y - (outcome.alpha + outcome.beta * x)
        frame = pd.DataFrame(residuals).dropna()
        if len(frame) < 60:
            continue
        rho_bar = _average_pairwise_correlation(frame)
        if rho_bar is None:
            continue
        csars = np.array([event_outcomes[asset].t_stat for asset in present], dtype=float)
        csars = csars[np.isfinite(csars)]
        n_assets = len(csars)
        if n_assets < 3:
            continue
        spread = float(csars.std(ddof=1))
        if spread <= 1e-12:
            continue
        bmp_t = float(csars.mean() / (spread / math.sqrt(n_assets)))
        inflation = math.sqrt(1.0 + (n_assets - 1) * rho_bar)
        kp_t = bmp_t / inflation
        mean_car_bps = float(np.mean([event_outcomes[asset].car_bps for asset in present]))
        rows.append(
            {
                "event_id": event_id,
                "event_day": days[idx].date().isoformat(),
                "n_assets": n_assets,
                "rho_bar": round(rho_bar, 4),
                "mean_car_bps": round(mean_car_bps, 2),
                "mean_csar": round(float(csars.mean()), 4),
                "sd_csar": round(spread, 4),
                "bmp_t": round(bmp_t, 2),
                "kp_t": round(kp_t, 2),
                "critical_t": _t_critical(n_assets - 1),
                "variance_inflation": round(inflation, 4),
            }
        )

    if not rows:
        return {
            "method": "Kolari-Pynnonen (2010) adjustment of BMP",
            "n_events": 0,
            "by_event": [],
        }
    bmp = np.array([row["bmp_t"] for row in rows])
    kp = np.array([row["kp_t"] for row in rows])
    event_means = np.array([row["mean_csar"] for row in rows])
    n_events = len(rows)
    naive_var = float(
        sum((row["sd_csar"] ** 2) / row["n_assets"] for row in rows) / n_events**2
    )
    kp_var = float(
        sum(
            (row["sd_csar"] ** 2) / row["n_assets"] * row["variance_inflation"] ** 2
            for row in rows
        )
        / n_events**2
    )
    pooled_mean = float(event_means.mean())
    return {
        "method": "Kolari-Pynnonen (2010) adjustment of BMP",
        "n_events": n_events,
        "n_asset_event_pairs": int(sum(row["n_assets"] for row in rows)),
        "mean_rho_bar": round(float(np.mean([row["rho_bar"] for row in rows])), 4),
        "mean_abs_bmp_t": round(float(np.mean(np.abs(bmp))), 2),
        "mean_abs_kp_t": round(float(np.mean(np.abs(kp))), 2),
        "share_significant_bmp": round(
            float(
                np.mean(
                    [
                        abs(row["bmp_t"]) > row["critical_t"]
                        for row in rows
                    ]
                )
            ),
            4,
        ),
        "share_significant_kp": round(
            float(
                np.mean(
                    [
                        abs(row["kp_t"]) > row["critical_t"]
                        for row in rows
                    ]
                )
            ),
            4,
        ),
        "mean_inflation": round(
            float(np.mean([row["variance_inflation"] for row in rows])), 4
        ),
        "pooled": {
            "mean_csar": round(pooled_mean, 4),
            "t_naive": round(pooled_mean / math.sqrt(naive_var), 2) if naive_var > 0 else None,
            "t_kp": round(pooled_mean / math.sqrt(kp_var), 2) if kp_var > 0 else None,
        },
        "by_event": rows,
    }
