"""Deterministic transmission aggregation.

The graph is a two-layer causal map:

    event -> transmission channel -> asset

Mechanism retrieval supplies signed channel weights. Channel specifications
supply asset loadings. The product is a signed, auditable exposure. This is
deliberately *not* an LLM-written graph: the language model can explain the
result, but it cannot change a sign or invent an edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..datasources.market import ASSET_LABELS, DEFAULT_ASSETS
from ..knowledge.loader import KnowledgeBase
from ..nlp.numbers import surprise_scale
from ..schemas import (
    AssetPrediction,
    ChannelActivation,
    EvidenceGrade,
    GraphEdge,
    GraphNode,
    GraphPayload,
    MacroEvent,
    MechanismMatch,
)

_GRADE_ORDER = {EvidenceGrade.A: 4, EvidenceGrade.B: 3, EvidenceGrade.C: 2, EvidenceGrade.D: 1}
_GRADE_DOWN = {
    EvidenceGrade.A: EvidenceGrade.B,
    EvidenceGrade.B: EvidenceGrade.C,
    EvidenceGrade.C: EvidenceGrade.C,
    EvidenceGrade.D: EvidenceGrade.D,
}


@dataclass
class TransmissionResult:
    channels: dict[str, ChannelActivation]
    asset_scores: dict[str, float]
    asset_contributions: dict[str, list[dict]]
    predictions: list[AssetPrediction]
    graph: GraphPayload
    matches: list[MechanismMatch]
    strength: float
    diagnostics: dict = field(default_factory=dict)


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


class TransmissionModel:
    def __init__(self, knowledge: KnowledgeBase, assets: list[str] | None = None):
        self.knowledge = knowledge
        self.assets = assets or DEFAULT_ASSETS
        for asset in self.assets:
            if not any(asset in channel.loadings for channel in knowledge.channels.values()):
                raise ValueError(f"asset {asset} has no channel loadings")

    def build(self, event: MacroEvent, matches: list[MechanismMatch]) -> TransmissionResult:
        strength = surprise_scale(event.event_type.value, event.surprise, event.magnitude)
        channels = self._activate_channels(matches)
        scores, contributions = self._asset_scores(channels)
        predictions = self._predictions(event, scores, contributions, matches, strength)
        graph = self._graph(event, channels, predictions, matches)
        diagnostics = {
            "n_mechanisms": len(matches),
            "strength": round(strength, 3),
            "channels_active": len(channels),
            "assets_active": sum(1 for p in predictions if not p.abstain),
        }
        return TransmissionResult(
            channels=channels,
            asset_scores=scores,
            asset_contributions=contributions,
            predictions=predictions,
            graph=graph,
            matches=matches,
            strength=strength,
            diagnostics=diagnostics,
        )

    # ------------------------------------------------------------- channels
    def _activate_channels(self, matches: list[MechanismMatch]) -> dict[str, ChannelActivation]:
        raw: dict[str, list[dict]] = {}
        for match in matches:
            for channel_id, weight in match.mechanism.channels.items():
                raw.setdefault(channel_id, []).append(
                    {
                        "mechanism_id": match.mechanism.id,
                        "mechanism_title": match.mechanism.title,
                        "weight": weight,
                        "score": match.score,
                        "contribution": weight * match.score,
                        "evidence_grade": match.mechanism.evidence_grade.value,
                    }
                )
        activations: dict[str, ChannelActivation] = {}
        for channel_id, rows in raw.items():
            spec = self.knowledge.channels[channel_id]
            total = sum(row["contribution"] for row in rows)
            denominator = max(1.0, sum(abs(row["contribution"]) for row in rows))
            score = max(-1.0, min(1.0, total / denominator))
            if abs(score) < 0.04:
                continue
            activations[channel_id] = ChannelActivation(
                channel=channel_id,
                name=spec.name,
                score=round(score, 4),
                contributions=sorted(rows, key=lambda row: -abs(row["contribution"])),
            )
        return activations

    # --------------------------------------------------------------- assets
    def _asset_scores(
        self, channels: dict[str, ChannelActivation]
    ) -> tuple[dict[str, float], dict[str, list[dict]]]:
        raw: dict[str, list[dict]] = {asset: [] for asset in self.assets}
        for channel_id, activation in channels.items():
            spec = self.knowledge.channels[channel_id]
            for asset, loading in spec.loadings.items():
                if asset not in raw:
                    continue
                raw[asset].append(
                    {
                        "channel": channel_id,
                        "channel_name": spec.name,
                        "channel_score": activation.score,
                        "loading": loading,
                        "contribution": activation.score * loading,
                        "scale_bps": spec.scale_bps,
                        "mechanisms": [row["mechanism_id"] for row in activation.contributions],
                    }
                )
        scores: dict[str, float] = {}
        contributions: dict[str, list[dict]] = {}
        for asset, rows in raw.items():
            total = sum(row["contribution"] for row in rows)
            # Saturating transform preserves magnitude differences instead of
            # normalising every one-sided asset to +/-1.
            scores[asset] = round(math.tanh(0.6 * total), 4)
            contributions[asset] = sorted(rows, key=lambda row: -abs(row["contribution"]))
        return scores, contributions

    def _predictions(
        self,
        event: MacroEvent,
        scores: dict[str, float],
        contributions: dict[str, list[dict]],
        matches: list[MechanismMatch],
        strength: float,
    ) -> list[AssetPrediction]:
        mechanism_by_id = {match.mechanism.id: match.mechanism for match in matches}
        predictions: list[AssetPrediction] = []
        for asset in self.assets:
            score = scores.get(asset, 0.0)
            rows = contributions.get(asset, [])
            mechanisms = []
            for row in rows:
                for mechanism_id in row["mechanisms"]:
                    if mechanism_id not in mechanisms:
                        mechanisms.append(mechanism_id)
            positives = sum(max(0.0, row["contribution"]) for row in rows)
            negatives = sum(max(0.0, -row["contribution"]) for row in rows)
            gross = positives + negatives
            conflict_ratio = (min(positives, negatives) / gross) if gross > 0 else 0.0
            conflicting = conflict_ratio > 0.2
            grades = [
                mechanism_by_id[mid].evidence_grade
                for mid in mechanisms
                if mid in mechanism_by_id
            ]
            best_grade = max(grades, key=lambda grade: _GRADE_ORDER[grade]) if grades else EvidenceGrade.C
            if conflict_ratio > 0.35:
                best_grade = _GRADE_DOWN[best_grade]
            abs_score = abs(score)
            confidence = 0.32 + 0.5 * abs_score
            if len(mechanisms) >= 2 and not conflicting:
                confidence += 0.06
            confidence -= 0.16 * conflict_ratio
            if best_grade == EvidenceGrade.A:
                confidence += 0.04
            elif best_grade == EvidenceGrade.C:
                confidence -= 0.08
            confidence *= 0.75 + 0.25 * event.confidence
            confidence = round(max(0.0, min(0.9, confidence)), 4)

            expected_bps = 0.0
            for row in rows:
                expected_bps += (
                    row["channel_score"]
                    * row["loading"]
                    * row["scale_bps"]
                    * min(strength, 2.0)
                    * 0.5
                )
            expected_bps = round(max(-1500.0, min(1500.0, expected_bps)), 1)

            abstain = abs_score < 0.03 or confidence < 0.22
            if abstain:
                p_up = 0.5
                direction = "flat"
            else:
                p_up = 0.5 + 0.45 * math.tanh(1.5 * score)
                p_up = round(max(0.05, min(0.95, p_up)), 4)
                direction = "up" if p_up >= 0.55 else "down" if p_up <= 0.45 else "flat"

            top_rows = rows[:3]
            rationale = "; ".join(
                f"{row['channel_name']} {row['channel_score']:+.2f} x loading {row['loading']:+.2f}"
                for row in top_rows
            )
            predictions.append(
                AssetPrediction(
                    asset=asset,
                    label=ASSET_LABELS.get(asset, asset),
                    direction=direction,
                    p_up=p_up,
                    confidence=confidence,
                    expected_car_bps=expected_bps,
                    horizon_days=max(
                        (mechanism_by_id[mid].horizon_days for mid in mechanisms if mid in mechanism_by_id),
                        default=5,
                    ),
                    evidence_grade=best_grade,
                    abstain=abstain,
                    channels=[row["channel"] for row in top_rows],
                    mechanisms=mechanisms,
                    rationale=rationale,
                    conflicting=conflicting,
                )
            )
        predictions.sort(key=lambda prediction: -abs(prediction.expected_car_bps))
        return predictions

    # ---------------------------------------------------------------- graph
    def _graph(
        self,
        event: MacroEvent,
        channels: dict[str, ChannelActivation],
        predictions: list[AssetPrediction],
        matches: list[MechanismMatch],
    ) -> GraphPayload:
        nodes: list[GraphNode] = [
            GraphNode(
                id="event",
                label=event.headline[:90],
                kind="event",
                layer=0,
                confidence=event.confidence,
                meta={
                    "event_type": event.event_type.value,
                    "direction": event.direction.value,
                    "magnitude": event.magnitude.model_dump() if event.magnitude else None,
                    "surprise": event.surprise.model_dump() if event.surprise else None,
                },
            )
        ]
        edges: list[GraphEdge] = []
        mechanism_by_id = {match.mechanism.id: match.mechanism for match in matches}
        active_channels = [cid for cid, act in channels.items() if abs(act.score) >= 0.05]
        for channel_id in active_channels:
            activation = channels[channel_id]
            spec = self.knowledge.channels[channel_id]
            nodes.append(
                GraphNode(
                    id=f"channel:{channel_id}",
                    label=spec.name,
                    kind="channel",
                    layer=1,
                    confidence=abs(activation.score),
                    meta={
                        "score": activation.score,
                        "description": spec.description,
                        "citations": spec.citations,
                    },
                )
            )
            for row in activation.contributions:
                mechanism = mechanism_by_id.get(row["mechanism_id"])
                if not mechanism:
                    continue
                edges.append(
                    GraphEdge(
                        source="event",
                        target=f"channel:{channel_id}",
                        sign=_sign(row["weight"]),
                        weight=round(abs(row["weight"] * row["score"]), 4),
                        mechanism_id=mechanism.id,
                        channel=channel_id,
                        evidence_grade=mechanism.evidence_grade,
                        rationale=mechanism.title,
                        citations=mechanism.citations,
                    )
                )

        for prediction in predictions:
            if prediction.abstain:
                continue
            nodes.append(
                GraphNode(
                    id=f"asset:{prediction.asset}",
                    label=prediction.asset,
                    kind="asset",
                    layer=2,
                    confidence=prediction.confidence,
                    meta={
                        "label": prediction.label,
                        "p_up": prediction.p_up,
                        "expected_car_bps": prediction.expected_car_bps,
                        "evidence_grade": prediction.evidence_grade.value,
                    },
                )
            )
            for row in self._rows_for_asset(prediction.asset, channels):
                activation = channels[row["channel"]]
                if abs(row["loading"]) < 0.05:
                    continue
                top_mechanism = activation.contributions[0]["mechanism_id"] if activation.contributions else ""
                mechanism = mechanism_by_id.get(top_mechanism)
                edges.append(
                    GraphEdge(
                        source=f"channel:{row['channel']}",
                        target=f"asset:{prediction.asset}",
                        # The edge sign is the *effect* on the asset, not the
                        # raw loading. A negative-loading asset (e.g. TLT on
                        # real yields) with a negative channel score is a
                        # positive effect and must render as such.
                        sign=_sign(row["contribution"]),
                        weight=round(abs(row["contribution"]), 4),
                        mechanism_id=top_mechanism,
                        channel=row["channel"],
                        evidence_grade=mechanism.evidence_grade if mechanism else prediction.evidence_grade,
                        rationale=(
                            f"{ASSET_LABELS.get(prediction.asset, prediction.asset)} exposure to "
                            f"{self.knowledge.channels[row['channel']].name.lower()}"
                        ),
                        citations=self.knowledge.channels[row["channel"]].citations,
                    )
                )
        return GraphPayload(nodes=nodes, edges=edges)

    def _rows_for_asset(self, asset: str, channels: dict[str, ChannelActivation]) -> list[dict]:
        rows = []
        for channel_id, activation in channels.items():
            if abs(activation.score) < 0.05:
                continue
            spec = self.knowledge.channels[channel_id]
            loading = spec.loadings.get(asset)
            if loading is None:
                continue
            rows.append(
                {
                    "channel": channel_id,
                    "channel_score": activation.score,
                    "loading": loading,
                    "contribution": activation.score * loading,
                }
            )
        return sorted(rows, key=lambda row: -abs(row["contribution"]))
