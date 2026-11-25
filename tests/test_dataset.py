from __future__ import annotations

from backend.app.evaluation.dataset import load_events, news_item, split_by_date
from backend.app.schemas import Direction, EventType


def test_event_dataset_loads_and_is_sorted():
    events = load_events()
    assert len(events) == 50
    dates = [event.published_at for event in events]
    assert dates == sorted(dates)
    assert len({event.id for event in events}) == len(events)


def test_event_labels_cover_all_types():
    events = load_events()
    types = {event.gold_event_type for event in events}
    assert EventType.MONETARY_POLICY in types
    assert EventType.INFLATION in types
    assert EventType.TRADE_POLICY in types
    assert EventType.GEOPOLITICS in types
    assert EventType.FINANCIAL_STABILITY in types
    assert EventType.CHINA_POLICY in types


def test_news_item_is_derived_from_event():
    event = load_events()[0]
    news = news_item(event)
    assert news.title == event.headline
    assert news.published_at == event.published_at
    assert news.source_name == event.source.name


def test_split_is_temporal_and_disjoint():
    events = load_events()
    train, test = split_by_date(events, 0.5)
    assert train and test
    assert max(event.published_at for event in train) <= min(event.published_at for event in test)
    assert {event.id for event in train}.isdisjoint({event.id for event in test})


def test_direction_enum_is_used():
    events = load_events()
    assert all(isinstance(event.gold_direction, Direction) for event in events)
