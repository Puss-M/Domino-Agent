from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.nlp.extractor import EventExtractor
from backend.app.schemas import Direction, EventType, NewsItem


def _event(text: str):
    extractor = EventExtractor()
    return extractor.extract(
        NewsItem(
            title=text,
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            source_name="test",
        )
    )


@pytest.mark.parametrize(
    "headline,event_type,direction",
    [
        ("Fed raises rates by 50 basis points", EventType.MONETARY_POLICY, Direction.TIGHTENING),
        ("Fed cuts rates by 25 basis points", EventType.MONETARY_POLICY, Direction.EASING),
        ("Fed holds rates steady but signals higher for longer", EventType.MONETARY_POLICY, Direction.HAWKISH_HOLD),
        ("US CPI rises 3.5% in March, above expectations", EventType.INFLATION, Direction.UPSIDE),
        ("US CPI rises 2.5% in August, below expectations", EventType.INFLATION, Direction.DOWNSIDE),
        ("OPEC+ agrees to cut oil production by 2 million barrels per day", EventType.ENERGY_SUPPLY, Direction.SUPPLY_CUT),
        ("US imposes new tariffs on Chinese goods", EventType.TRADE_POLICY, Direction.ESCALATION),
        ("Trump pauses reciprocal tariffs for 90 days", EventType.TRADE_POLICY, Direction.DEESCALATION),
        ("Russia invades Ukraine", EventType.GEOPOLITICS, Direction.RISK_OFF),
        ("SVB collapse triggers a bank run", EventType.FINANCIAL_STABILITY, Direction.STRESS),
        ("China unveils a stimulus package and cuts the reserve requirement ratio", EventType.CHINA_POLICY, Direction.STIMULUS),
        ("Bank of Japan raises its policy rate to 0.25%", EventType.MONETARY_POLICY, Direction.TIGHTENING),
        ("US payrolls rise by 114,000, much weaker than expected", EventType.LABOR_MARKET, Direction.DOWNSIDE),
    ],
)
def test_headline_classification(headline, event_type, direction):
    event = _event(headline)
    assert event.event_type == event_type
    assert event.direction == direction


def test_actor_and_magnitude_are_extracted():
    event = _event("Fed raises rates by 50 basis points")
    assert event.actor == "US_FED"
    assert event.magnitude is not None
    assert event.magnitude.value == 50
    assert event.magnitude.unit == "bps"


def test_chinese_headline():
    event = _event("美联储加息50个基点")
    assert event.event_type == EventType.MONETARY_POLICY
    assert event.direction == Direction.TIGHTENING
    assert event.magnitude is not None
    assert event.magnitude.value == 50


def test_hawkish_hold_is_not_a_hike():
    event = _event("Fed holds rates steady but signals higher for longer")
    assert event.direction == Direction.HAWKISH_HOLD
    assert event.direction != Direction.TIGHTENING


def test_unknown_headline_is_low_confidence_other():
    event = _event("A company appoints a new marketing director")
    assert event.event_type == EventType.OTHER
    assert event.confidence < 0.5
