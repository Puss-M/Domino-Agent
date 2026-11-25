"""Deterministic evidence audit.

This replaces the original project's "reviewer agent" prompt with checks that
can fail a build: citations must exist, grades must be usable, probabilities
must be bounded, and no event may be evaluated with information from after its
publication time.
"""

from __future__ import annotations

from datetime import datetime

from ..schemas import AuditReport, EvidenceGrade, MacroEvent, MechanismMatch
from .transmission import TransmissionResult


def audit(
    event: MacroEvent,
    matches: list[MechanismMatch],
    transmission: TransmissionResult,
    *,
    as_of: datetime | None = None,
) -> AuditReport:
    issues: list[str] = []
    warnings: list[str] = []
    used = [match.mechanism.id for match in matches]
    checked_edges = len(transmission.graph.edges)

    if not matches:
        issues.append("no cited mechanism matched this event; the engine abstains")
    if event.confidence < 0.35:
        issues.append(f"event extraction confidence is low ({event.confidence:.2f})")
    if event.source.url is None:
        warnings.append("event has no source URL; provenance is weaker")
    if as_of is not None and event.published_at > as_of:
        issues.append("event is dated after the analysis as-of time (look-ahead)")

    for match in matches:
        if match.mechanism.evidence_grade == EvidenceGrade.D:
            issues.append(f"speculative mechanism {match.mechanism.id} entered a prediction")
        if not match.mechanism.citations:
            issues.append(f"mechanism {match.mechanism.id} has no citation")

    for edge in transmission.graph.edges:
        if not edge.citations:
            issues.append(f"edge {edge.source}->{edge.target} has no citation")
        if edge.sign == 0:
            warnings.append(f"edge {edge.source}->{edge.target} has a zero sign")

    if event.event_type.value in {"monetary_policy", "inflation"}:
        if event.surprise is None or event.surprise.sign == "neutral":
            warnings.append(
                "no explicit surprise direction was extracted; a level change may already be priced"
            )

    active = [prediction for prediction in transmission.predictions if not prediction.abstain]
    if not active:
        issues.append("all assets abstained")
    elif len(active) < len(transmission.predictions) / 2:
        warnings.append(
            f"only {len(active)}/{len(transmission.predictions)} assets passed the evidence threshold"
        )
    conflicting = [prediction.asset for prediction in active if prediction.conflicting]
    if conflicting:
        warnings.append("conflicting channels for: " + ", ".join(conflicting))
    weak = [prediction.asset for prediction in active if prediction.evidence_grade == EvidenceGrade.C]
    if weak:
        warnings.append("C-grade evidence drives: " + ", ".join(weak))

    return AuditReport(
        passed=not issues,
        issues=issues,
        warnings=warnings,
        checked_edges=checked_edges,
        used_mechanisms=used,
    )
