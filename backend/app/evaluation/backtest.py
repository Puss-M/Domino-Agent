"""Walk-forward backtest and event-study evaluation.

The evaluation deliberately separates three things that are often conflated:

1. extraction quality (did the pipeline read the event correctly?);
2. transmission quality (did the signed asset views match realised CAR signs?);
3. calibration (are the stated probabilities usable?).

Only the stack weights and Platt calibration are fitted, and only on the first
half of the events. Analog priors use matured prior events; the mechanism
library is fixed. The test split is untouched by any fitting step.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from ..config import Settings, get_settings
from ..datasources.market import DEFAULT_ASSETS, MarketData
from ..reasoning.engine import AnalysisEngine
from ..schemas import (
    AssetMetrics,
    BacktestConfig,
    BacktestEventResult,
    BacktestResponse,
    CalibrationBin,
    EventTypeMetrics,
    ExtractionMetrics,
    ModelMetrics,
    Provenance,
)
from .analog import AnalogModel
from .dataset import load_events, split_by_date
from .event_study import compute_outcomes
from .metrics import (
    accuracy,
    apply_platt,
    brier,
    calibration_bins,
    fit_platt,
    summarize,
)


def _logit(p: float) -> float:
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, x))))


def _fit_stack_weights(rows: list[dict]) -> tuple[float, float, float]:
    """Fit non-negative logit weights on the training split by Brier score."""
    best = (1.0, 0.4, 0.3)
    best_score = float("inf")
    for w_mech in (0.6, 0.8, 1.0, 1.2):
        for w_analog in (0.0, 0.2, 0.4, 0.6):
            for w_base in (0.0, 0.2, 0.4, 0.6):
                if w_mech == 0 and w_analog == 0 and w_base == 0:
                    continue
                candidates = [
                    {**row, "p_up": _stack_p(row, (w_mech, w_analog, w_base))}
                    for row in rows
                ]
                if not any(row.get("y") in {0, 1} for row in candidates):
                    continue
                score = brier(candidates)
                if score is None:
                    continue
                if score < best_score - 1e-9 or (
                    abs(score - best_score) <= 1e-9 and w_mech > best[0]
                ):
                    best_score = score
                    best = (w_mech, w_analog, w_base)
    return best


def _stack_p(row: dict, weights: tuple[float, float, float]) -> float | None:
    p_mech = row.get("p_mech", row.get("mechanism"))
    p_analog = row.get("p_analog", row.get("analog"))
    p_base = row.get("p_base", row.get("base_rate"))
    if p_mech is None and p_analog is None:
        return None
    w_mech, w_analog, w_base = weights
    z = 0.0
    if p_mech is not None:
        z += w_mech * _logit(p_mech)
    if p_analog is not None:
        z += w_analog * _logit(p_analog)
    if p_base is not None:
        z += w_base * _logit(p_base)
    return _sigmoid(z)


class BacktestEngine:
    def __init__(
        self,
        settings: Settings | None = None,
        assets: list[str] | None = None,
        config: BacktestConfig | None = None,
    ):
        self.settings = settings or get_settings()
        self.config = config or BacktestConfig()
        self.assets = assets or self.config.assets or DEFAULT_ASSETS
        self.market = MarketData(self.settings)
        self.engine = AnalysisEngine(settings=self.settings, assets=self.assets)
        self.knowledge = self.engine.knowledge

    def run(self, config: BacktestConfig | None = None) -> BacktestResponse:
        config = config or self.config
        events = load_events(settings=self.settings)
        if config.include_events:
            wanted = set(config.include_events)
            events = [event for event in events if event.id in wanted]
        prices = self.market.prices_wide("adj_close", self.assets + ["SPY"])
        prices = prices.dropna(how="all")
        outcomes, skipped = compute_outcomes(events, prices, self.assets, config)

        rows_by_model: dict[str, list[dict]] = defaultdict(list)
        event_results: list[BacktestEventResult] = []
        extraction_pairs: list[tuple[str, str, str, str]] = []
        matured: list = []
        pending: list = []
        base_counts: dict[str, list[int]] = defaultdict(list)

        for event in sorted(events, key=lambda item: item.published_at):
            event_outcomes = outcomes.get(event.id, {})
            if not event_outcomes:
                continue
            current_day = next(iter(event_outcomes.values())).event_day

            # Move prior events whose outcome window has fully matured.
            still_pending = []
            for prior in pending:
                prior_outcomes = outcomes.get(prior.id, {})
                if not prior_outcomes:
                    continue
                window_end = max(outcome.window_end for outcome in prior_outcomes.values())
                if window_end < current_day:
                    matured.append(prior)
                else:
                    still_pending.append(prior)
            pending = still_pending

            analog = AnalogModel().fit(matured, outcomes)
            base_predictions = {
                asset: (sum(base_counts[asset]) + 1) / (len(base_counts[asset]) + 2)
                if base_counts[asset]
                else 0.5
                for asset in self.assets
            }

            response = self.engine.analyze_labeled(event)
            extracted = response.event
            analog_predictions = analog.predict(
                event, event_type=extracted.event_type, direction=extracted.direction
            )
            mechanism_predictions = {
                prediction.asset: prediction.p_up
                for prediction in response.predictions
                if not prediction.abstain
            }
            extraction_pairs.append(
                (
                    event.gold_event_type.value,
                    extracted.event_type.value,
                    event.gold_direction.value,
                    extracted.direction.value,
                )
            )

            event_predictions: dict[str, dict] = {}
            event_realized: dict[str, dict] = {}
            extraction_correct = {
                "event_type": extracted.event_type == event.gold_event_type,
                "direction": extracted.direction == event.gold_direction,
                "joint": (
                    extracted.event_type == event.gold_event_type
                    and extracted.direction == event.gold_direction
                ),
            }
            for asset, outcome in event_outcomes.items():
                y = 1 if outcome.direction == "up" else 0 if outcome.direction == "down" else None
                p_mech = mechanism_predictions.get(asset)
                p_analog = analog_predictions[asset].p_up if asset in analog_predictions else None
                p_base = base_predictions.get(asset, 0.5)
                if p_mech is not None and p_analog is not None:
                    p_hybrid = _sigmoid(_logit(p_mech) + 0.5 * _logit(p_analog))
                elif p_mech is not None:
                    p_hybrid = p_mech
                elif p_analog is not None:
                    p_hybrid = p_analog
                else:
                    p_hybrid = None

                base = {
                    "event_id": event.id,
                    "asset": asset,
                    "event_type": event.gold_event_type.value,
                    "direction": event.gold_direction.value,
                    "y": y,
                    "car_bps": outcome.car_bps,
                    "outcome_direction": outcome.direction,
                    "p_mech": p_mech,
                    "p_analog": p_analog,
                    "p_base": p_base,
                }
                rows_by_model["mechanism"].append({**base, "p_up": p_mech})
                rows_by_model["analog"].append({**base, "p_up": p_analog})
                rows_by_model["hybrid"].append({**base, "p_up": p_hybrid})
                rows_by_model["always_up"].append({**base, "p_up": p_base})
                rows_by_model["coin_flip"].append({**base, "p_up": 0.5})

                event_predictions[asset] = {
                    "mechanism": p_mech,
                    "analog": p_analog,
                    "hybrid": round(p_hybrid, 4) if p_hybrid is not None else None,
                    "base_rate": round(p_base, 4),
                    "analog_n": analog_predictions[asset].n if asset in analog_predictions else 0,
                    "analog_mean_car_bps": (
                        analog_predictions[asset].mean_car_bps if asset in analog_predictions else None
                    ),
                }
                event_realized[asset] = outcome.to_dict()

                if y is not None:
                    base_counts[asset].append(y)
            pending.append(event)

            event_results.append(
                BacktestEventResult(
                    event_id=event.id,
                    date=current_day,
                    headline=event.headline,
                    event_type=event.gold_event_type.value,
                    direction=event.gold_direction.value,
                    session=event.session,
                    predictions=event_predictions,
                    realized=event_realized,
                    extraction_correct=extraction_correct,
                )
            )

        # ---------------------------------------------------------- calibration
        train_events, test_events = split_by_date(events, config.train_fraction)
        train_ids = {event.id for event in train_events}
        test_ids = {event.id for event in test_events}
        hybrid_rows = rows_by_model["hybrid"]
        train_rows = [row for row in hybrid_rows if row["event_id"] in train_ids]
        test_rows = [row for row in hybrid_rows if row["event_id"] in test_ids]
        stack_weights = _fit_stack_weights(train_rows)
        stacked_rows = [{**row, "p_up": _stack_p(row, stack_weights)} for row in hybrid_rows]
        stacked_train = [row for row in stacked_rows if row["event_id"] in train_ids]
        stacked_test = [row for row in stacked_rows if row["event_id"] in test_ids]

        hybrid_platt = fit_platt(train_rows)
        stacked_platt = fit_platt(stacked_train)
        mechanism_platt = fit_platt(
            [row for row in rows_by_model["mechanism"] if row["event_id"] in train_ids]
        )
        analog_platt = fit_platt(
            [row for row in rows_by_model["analog"] if row["event_id"] in train_ids]
        )
        calibrated_rows = [
            {**row, "p_up": apply_platt(row["p_up"], hybrid_platt)} for row in test_rows
        ]
        stacked_calibrated_rows = [
            {**row, "p_up": apply_platt(row["p_up"], stacked_platt)} for row in stacked_test
        ]

        test_models = {
            "always_up_test": [
                row for row in rows_by_model["always_up"] if row["event_id"] in test_ids
            ],
            "coin_flip_test": [
                row for row in rows_by_model["coin_flip"] if row["event_id"] in test_ids
            ],
            "mechanism_test": [
                row for row in rows_by_model["mechanism"] if row["event_id"] in test_ids
            ],
            "analog_test": [
                row for row in rows_by_model["analog"] if row["event_id"] in test_ids
            ],
            "hybrid_test": test_rows,
            "stacked_test": stacked_test,
            "mechanism_calibrated_test": [
                {**row, "p_up": apply_platt(row["p_up"], mechanism_platt)}
                for row in rows_by_model["mechanism"]
                if row["event_id"] in test_ids
            ],
            "analog_calibrated_test": [
                {**row, "p_up": apply_platt(row["p_up"], analog_platt)}
                for row in rows_by_model["analog"]
                if row["event_id"] in test_ids
            ],
            "hybrid_calibrated_test": calibrated_rows,
            "stacked_calibrated_test": stacked_calibrated_rows,
        }
        total_candidates = sum(
            1 for row in test_rows if row.get("outcome_direction") in {"up", "down"}
        )
        metrics = [
            summarize(name, rows, total_candidates, bootstrap_samples=config.bootstrap_samples)
            for name, rows in test_models.items()
        ]

        # Attach the stacked probabilities to the per-event detail.
        for result in event_results:
            for asset, prediction in result.predictions.items():
                row = {
                    "p_mech": prediction.get("mechanism"),
                    "p_analog": prediction.get("analog"),
                    "p_base": prediction.get("base_rate"),
                }
                p_stack = _stack_p(row, stack_weights)
                prediction["stacked"] = round(p_stack, 4) if p_stack is not None else None
                prediction["stacked_calibrated"] = (
                    apply_platt(p_stack, stacked_platt) if p_stack is not None else None
                )

        # ----------------------------------------------------------- breakdown
        chosen_rows = stacked_calibrated_rows
        by_asset = []
        for asset in self.assets:
            asset_rows = [row for row in chosen_rows if row["asset"] == asset]
            predicted = [
                row for row in asset_rows if row.get("p_up") is not None and row.get("y") in {0, 1}
            ]
            by_asset.append(
                AssetMetrics(
                    asset=asset,
                    n=len(predicted),
                    accuracy=_round(accuracy(predicted)),
                    brier=_round(brier(predicted)),
                    mean_car_bps=(
                        round(sum(row["car_bps"] for row in predicted) / len(predicted), 2)
                        if predicted
                        else None
                    ),
                )
            )
        by_type = []
        for event_type in sorted({row["event_type"] for row in chosen_rows}):
            type_rows = [row for row in chosen_rows if row["event_type"] == event_type]
            predicted = [
                row for row in type_rows if row.get("p_up") is not None and row.get("y") in {0, 1}
            ]
            by_type.append(
                EventTypeMetrics(
                    event_type=event_type,
                    n_events=len({row["event_id"] for row in type_rows}),
                    n_predictions=len(predicted),
                    accuracy=_round(accuracy(predicted)),
                    brier=_round(brier(predicted)),
                )
            )

        calibration = [
            CalibrationBin(**bucket) for bucket in calibration_bins(calibrated_rows, bins=8, strategy="quantile")
        ]

        extraction = self._extraction_metrics(extraction_pairs)
        notes = [
            "Only the stack weights and Platt calibration are fitted, on the first half of the events; all other components are fixed or walk-forward.",
            "Analog priors use only prior events whose outcome window has matured before the current event.",
            "The sample is small and event windows overlap; the bootstrap resamples events, not asset rows.",
            "Mechanism priors were authored by the project, not preregistered, and were not fitted to these outcomes.",
            f"Stack weights fitted on train: mechanism={stack_weights[0]:.2f}, analog={stack_weights[1]:.2f}, base_rate={stack_weights[2]:.2f}.",
            f"Platt parameters (stacked): a={stacked_platt[0]:.2f}, b={stacked_platt[1]:.2f}.",
            (
                f"Skipped {len(skipped)} events for insufficient price history."
                if skipped
                else "No events were skipped for price history."
            ),
        ]
        provenance = Provenance(
            sources=[
                "events: backend/data/events/events.yaml",
                "prices: backend/data/market/prices.csv",
                f"knowledge: {self.knowledge.path.name} v{self.knowledge.version}",
                "extraction: rules-v1",
            ],
            retrieved_at=datetime.now(timezone.utc),
            as_of=max(event.published_at for event in events),
            snapshot_version="local",
            notes=[
                "Adjusted closes are revised after corporate actions; this is not a point-in-time price database.",
                "Event labels are editorial; market outcomes are computed independently.",
            ],
        )
        return BacktestResponse(
            config=config,
            n_events=len(event_results),
            n_outcome_observations=sum(
                1
                for row in rows_by_model["hybrid"]
                if row.get("outcome_direction") in {"up", "down"}
            ),
            metrics=[ModelMetrics(**metric) for metric in metrics],
            by_asset=by_asset,
            by_event_type=by_type,
            calibration=calibration,
            extraction=extraction,
            events=event_results,
            provenance=provenance,
            notes=notes,
        )

    @staticmethod
    def _extraction_metrics(pairs: list[tuple[str, str, str, str]]) -> ExtractionMetrics:
        if not pairs:
            return ExtractionMetrics(
                n=0, event_type_accuracy=0.0, direction_accuracy=0.0, joint_accuracy=0.0
            )
        type_ok = sum(1 for gold, pred, _, _ in pairs if gold == pred)
        dir_ok = sum(1 for _, _, gold, pred in pairs if gold == pred)
        joint_ok = sum(
            1 for gold, pred, gold_dir, pred_dir in pairs if gold == pred and gold_dir == pred_dir
        )
        confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for gold, pred, _, _ in pairs:
            confusion[gold][pred] += 1
        return ExtractionMetrics(
            n=len(pairs),
            event_type_accuracy=round(type_ok / len(pairs), 4),
            direction_accuracy=round(dir_ok / len(pairs), 4),
            joint_accuracy=round(joint_ok / len(pairs), 4),
            confusion={gold: dict(counts) for gold, counts in confusion.items()},
        )


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
