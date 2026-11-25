"""Historical-analog baseline.

This is the quantitative memory the original project lacked: before predicting
a new event, look at what happened to each asset after *matured* prior events
of the same type and direction. It is deliberately simple, expanding-window
and strongly shrunk, so it is a hard-to-beat baseline rather than a tuned model.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..schemas import Direction, LabeledEvent
from .event_study import Outcome


def direction_bucket(direction: Direction) -> str:
    if direction in {Direction.TIGHTENING, Direction.HAWKISH_HOLD}:
        return "tightening"
    if direction in {Direction.EASING, Direction.DOVISH_HOLD}:
        return "easing"
    return direction.value


@dataclass
class AnalogPrediction:
    asset: str
    p_up: float
    n: int
    mean_car_bps: float
    confidence: float


class AnalogModel:
    def __init__(self, min_analogs: int = 2, prior_alpha: float = 1.5):
        self.min_analogs = min_analogs
        self.prior_alpha = prior_alpha
        self.stats: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.n_events = 0

    def fit(
        self, events: list[LabeledEvent], outcomes: dict[str, dict[str, Outcome]]
    ) -> "AnalogModel":
        stats: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        count = 0
        for event in events:
            event_outcomes = outcomes.get(event.id, {})
            if not event_outcomes:
                continue
            key = (event.gold_event_type.value, direction_bucket(event.gold_direction))
            for asset, outcome in event_outcomes.items():
                if outcome.direction == "flat":
                    continue
                stats[key][asset].append(outcome.car_bps)
            count += 1
        self.stats = stats
        self.n_events = count
        return self

    def predict(
        self,
        event: LabeledEvent,
        *,
        event_type=None,
        direction=None,
    ) -> dict[str, AnalogPrediction]:
        # The current event must be classified by the pipeline; the historical
        # analogs use their curated labels because those are known ex post.
        current_type = event_type or event.gold_event_type
        current_direction = direction or event.gold_direction
        key = (current_type.value, direction_bucket(current_direction))
        asset_stats = self.stats.get(key, {})
        predictions: dict[str, AnalogPrediction] = {}
        for asset, cars in asset_stats.items():
            n = len(cars)
            if n < self.min_analogs:
                continue
            up = sum(1 for car in cars if car > 0)
            p_up = (up + self.prior_alpha) / (n + 2 * self.prior_alpha)
            predictions[asset] = AnalogPrediction(
                asset=asset,
                p_up=round(p_up, 4),
                n=n,
                mean_car_bps=round(sum(cars) / n, 2),
                confidence=round(n / (n + 8), 4),
            )
        return predictions
