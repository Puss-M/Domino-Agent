"""Forecast-evaluation metrics with event-clustered uncertainty.

Predictions for different assets on the same event are correlated. The
bootstrap therefore resamples *events*, not individual asset predictions; this
is the same clustering logic used in event-study inference.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict


def _clip(value: float, low: float = 1e-6, high: float = 1 - 1e-6) -> float:
    return max(low, min(high, value))


def brier(rows: list[dict]) -> float | None:
    valid = [row for row in rows if row.get("y") in {0, 1} and row.get("p_up") is not None]
    if not valid:
        return None
    return sum((row["p_up"] - row["y"]) ** 2 for row in valid) / len(valid)


def log_loss(rows: list[dict]) -> float | None:
    valid = [row for row in rows if row.get("y") in {0, 1} and row.get("p_up") is not None]
    if not valid:
        return None
    total = 0.0
    for row in valid:
        p = _clip(row["p_up"])
        total += -(row["y"] * math.log(p) + (1 - row["y"]) * math.log(1 - p))
    return total / len(valid)


def accuracy(rows: list[dict]) -> float | None:
    valid = [
        row
        for row in rows
        if row.get("y") in {0, 1} and row.get("p_up") is not None and row["p_up"] != 0.5
    ]
    if not valid:
        return None
    return sum(int((row["p_up"] > 0.5) == bool(row["y"])) for row in valid) / len(valid)


def auc(rows: list[dict]) -> float | None:
    valid = [row for row in rows if row.get("y") in {0, 1} and row.get("p_up") is not None]
    positives = [row["p_up"] for row in valid if row["y"] == 1]
    negatives = [row["p_up"] for row in valid if row["y"] == 0]
    if not positives or not negatives:
        return None
    # Rank-based AUC with tie handling.
    wins = 0.0
    for pos in positives:
        for neg in negatives:
            wins += 1.0 if pos > neg else 0.5 if pos == neg else 0.0
    return wins / (len(positives) * len(negatives))


def expected_calibration_error(rows: list[dict], bins: int = 10) -> float | None:
    valid = [row for row in rows if row.get("y") in {0, 1} and row.get("p_up") is not None]
    if not valid:
        return None
    buckets: list[list[dict]] = [[] for _ in range(bins)]
    for row in valid:
        index = min(bins - 1, int(row["p_up"] * bins))
        buckets[index].append(row)
    total = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        mean_pred = sum(row["p_up"] for row in bucket) / len(bucket)
        observed = sum(row["y"] for row in bucket) / len(bucket)
        total += (len(bucket) / len(valid)) * abs(mean_pred - observed)
    return total


def calibration_bins(
    rows: list[dict], bins: int = 10, strategy: str = "equal"
) -> list[dict]:
    valid = [row for row in rows if row.get("y") in {0, 1} and row.get("p_up") is not None]
    if not valid:
        return []
    if strategy == "quantile":
        ordered = sorted(valid, key=lambda row: row["p_up"])
        chunk = max(1, len(ordered) // bins)
        buckets = [ordered[index : index + chunk] for index in range(0, len(ordered), chunk)]
        if len(buckets) > bins:
            buckets[-2].extend(buckets[-1])
            buckets.pop()
    else:
        buckets = []
        for index in range(bins):
            lower, upper = index / bins, (index + 1) / bins
            bucket = [
                row
                for row in valid
                if lower <= row["p_up"] < upper
                or (index == bins - 1 and row["p_up"] == 1.0)
            ]
            if bucket:
                buckets.append(bucket)
    result = []
    for bucket in buckets:
        if not bucket:
            continue
        predictions = [row["p_up"] for row in bucket]
        result.append(
            {
                "bin_lower": round(min(predictions), 4),
                "bin_upper": round(max(predictions), 4),
                "n": len(bucket),
                "mean_predicted": round(sum(predictions) / len(bucket), 4),
                "observed_frequency": round(sum(row["y"] for row in bucket) / len(bucket), 4),
            }
        )
    return result


def _cluster_resample(rows: list[dict], rng: random.Random) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.get("event_id", "_")].append(row)
    keys = list(grouped)
    sample = [rng.choice(keys) for _ in keys]
    out: list[dict] = []
    for key in sample:
        out.extend(grouped[key])
    return out


def bootstrap_ci(
    rows: list[dict],
    metric_fn,
    samples: int = 500,
    seed: int = 7,
    alpha: float = 0.05,
) -> tuple[float, float] | None:
    if not rows:
        return None
    clusters = {row.get("event_id", "_") for row in rows}
    if len(clusters) < 5:
        # A bootstrap over two or three events is not an interval; do not
        # present it as one.
        return None
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        resample = _cluster_resample(rows, rng)
        value = metric_fn(resample)
        if value is not None:
            estimates.append(value)
    if len(estimates) < 20:
        return None
    estimates.sort()
    low = estimates[int((alpha / 2) * len(estimates))]
    high = estimates[int((1 - alpha / 2) * len(estimates)) - 1]
    return (round(low, 4), round(high, 4))


def summarize(
    model: str,
    rows: list[dict],
    total_candidates: int,
    *,
    bootstrap_samples: int = 500,
) -> dict:
    predicted = [
        row for row in rows if row.get("p_up") is not None and row.get("y") in {0, 1}
    ]
    coverage = len(predicted) / total_candidates if total_candidates else 0.0
    return {
        "model": model,
        "n": len(predicted),
        "coverage": round(coverage, 4),
        "accuracy": _round(accuracy(predicted)),
        "brier": _round(brier(predicted)),
        "log_loss": _round(log_loss(predicted)),
        "auc": _round(auc(predicted)),
        "ece": _round(expected_calibration_error(predicted)),
        "accuracy_ci": bootstrap_ci(predicted, accuracy, samples=bootstrap_samples),
        "brier_ci": bootstrap_ci(predicted, brier, samples=bootstrap_samples),
    }


def paired_bootstrap_difference(
    rows_a: list[dict],
    rows_b: list[dict],
    samples: int = 500,
    seed: int = 7,
) -> dict:
    """Paired Brier difference (A - B), clustered by event.

    Negative delta means model A has the lower Brier score. The p-value is the
    one-sided bootstrap probability that the difference is non-negative
    (i.e. evidence against A being better).
    """
    index_a = {
        (row.get("event_id"), row.get("asset")): row
        for row in rows_a
        if row.get("p_up") is not None and row.get("y") in {0, 1}
    }
    index_b = {
        (row.get("event_id"), row.get("asset")): row
        for row in rows_b
        if row.get("p_up") is not None and row.get("y") in {0, 1}
    }
    keys = sorted(set(index_a) & set(index_b), key=lambda key: (str(key[0]), str(key[1])))
    if len(keys) < 10:
        return {"delta_brier": None, "ci": None, "p_value": None, "n_pairs": len(keys)}
    pairs = [
        {
            "event_id": key[0],
            "asset": key[1],
            "y": index_a[key]["y"],
            "a": index_a[key]["p_up"],
            "b": index_b[key]["p_up"],
        }
        for key in keys
    ]
    delta = sum((row["a"] - row["y"]) ** 2 - (row["b"] - row["y"]) ** 2 for row in pairs) / len(pairs)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in pairs:
        grouped[row["event_id"]].append(row)
    event_ids = list(grouped)
    if len(event_ids) < 5:
        return {"delta_brier": round(delta, 4), "ci": None, "p_value": None, "n_pairs": len(pairs)}
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        sampled = [rng.choice(event_ids) for _ in event_ids]
        rows = [row for event_id in sampled for row in grouped[event_id]]
        deltas.append(
            sum((row["a"] - row["y"]) ** 2 - (row["b"] - row["y"]) ** 2 for row in rows) / len(rows)
        )
    deltas.sort()
    low = deltas[int(0.025 * len(deltas))]
    high = deltas[int(0.975 * len(deltas)) - 1]
    p_value = sum(value >= 0 for value in deltas) / len(deltas)
    return {
        "delta_brier": round(delta, 4),
        "ci": (round(low, 4), round(high, 4)),
        "p_value": round(p_value, 4),
        "n_pairs": len(pairs),
    }


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def fit_platt(rows: list[dict]) -> tuple[float, float]:
    """One-dimensional logistic calibration: p_cal = sigmoid(a * logit(p) + b)."""
    valid = [
        row for row in rows if row.get("y") in {0, 1} and row.get("p_up") is not None
    ]
    if len(valid) < 30:
        return 1.0, 0.0
    z = [_logit(row["p_up"]) for row in valid]
    y = [row["y"] for row in valid]
    a, b = 1.0, 0.0
    learning_rate = 0.1
    for _ in range(400):
        grad_a = grad_b = 0.0
        for zi, yi in zip(z, y, strict=False):
            p = _sigmoid(a * zi + b)
            error = p - yi
            grad_a += error * zi
            grad_b += error
        a -= learning_rate * (grad_a / len(valid) + 0.01 * (a - 1.0))
        b -= learning_rate * (grad_b / len(valid) + 0.01 * b)
    return round(a, 4), round(b, 4)


def apply_platt(p_up: float | None, params: tuple[float, float]) -> float | None:
    if p_up is None:
        return None
    a, b = params
    return round(_sigmoid(a * _logit(p_up) + b), 4)


def _logit(p: float) -> float:
    p = _clip(p)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, x))))
