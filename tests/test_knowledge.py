from __future__ import annotations

from datetime import datetime, timezone

from backend.app.knowledge.retrieval import MechanismRetriever
from backend.app.schemas import Direction, EventType, MacroEvent, SourceRef


def _event(headline: str, event_type: EventType, direction: Direction, actor: str | None = None):
    return MacroEvent(
        id="test",
        headline=headline,
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        source=SourceRef(name="test"),
        event_type=event_type,
        direction=direction,
        actor=actor,
        confidence=0.9,
    )


def test_all_mechanisms_are_cited(knowledge):
    assert len(knowledge.mechanisms) >= 15
    for mechanism in knowledge.mechanisms:
        assert mechanism.citations
        assert mechanism.rationale
        for channel in mechanism.channels:
            assert channel in knowledge.channels


def test_hawkish_hike_retrieves_tightening_mechanism(knowledge):
    retriever = MechanismRetriever(knowledge)
    event = _event("Fed raises rates by 50 basis points", EventType.MONETARY_POLICY, Direction.TIGHTENING, "US_FED")
    matches = retriever.match(event)
    assert [match.mechanism.id for match in matches] == ["MON_TIGHTEN"]


def test_emergency_cut_retrieves_stress_mechanism(knowledge):
    retriever = MechanismRetriever(knowledge)
    event = _event(
        "Fed cuts rates by 50 basis points in emergency move amid a banking crisis",
        EventType.MONETARY_POLICY,
        Direction.EASING,
        "US_FED",
    )
    ids = [match.mechanism.id for match in retriever.match(event)]
    assert "MON_EASE_STRESS" in ids
    assert "MON_EASE_INSURANCE" not in ids


def test_boj_actor_uses_funding_mechanism(knowledge):
    retriever = MechanismRetriever(knowledge)
    event = _event(
        "Bank of Japan raises its policy rate to 0.25%",
        EventType.MONETARY_POLICY,
        Direction.TIGHTENING,
        "BOJ",
    )
    ids = [match.mechanism.id for match in retriever.match(event)]
    assert ids == ["BOJ_HIKE"]


def test_ecb_actor_uses_ecb_mechanism(knowledge):
    retriever = MechanismRetriever(knowledge)
    event = _event(
        "ECB raises rates by 50 basis points",
        EventType.MONETARY_POLICY,
        Direction.TIGHTENING,
        "ECB",
    )
    ids = [match.mechanism.id for match in retriever.match(event)]
    assert ids == ["ECB_HIKE"]


def test_unmatched_event_has_no_mechanism(knowledge):
    retriever = MechanismRetriever(knowledge)
    event = _event("A company appoints a new marketing director", EventType.OTHER, Direction.NEUTRAL)
    assert retriever.match(event) == []
