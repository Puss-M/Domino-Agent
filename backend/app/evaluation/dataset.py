"""Hand-curated, dated event sample used for extraction and event-study tests.

The labels are editorial: event type and direction are assigned from the
official action and the published consensus, not from the market reaction.
Market outcomes are computed separately from the price snapshot. Keeping the
label and the outcome separate is what makes the evaluation non-circular.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..schemas import (
    Direction,
    EventType,
    LabeledEvent,
    Magnitude,
    NewsItem,
    SourceRef,
    SourceTier,
    Surprise,
)

ET = ZoneInfo("America/New_York")


class DatasetError(RuntimeError):
    pass


def _published_at(date_value: str | dt.date, time_et: str | None) -> datetime:
    if isinstance(date_value, dt.date):
        day = date_value
    else:
        day = dt.date.fromisoformat(str(date_value))
    if time_et:
        hour, minute = (int(part) for part in time_et.split(":"))
    else:
        hour, minute = 12, 0
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)


def load_events(
    path: Path | None = None, settings: Settings | None = None
) -> list[LabeledEvent]:
    settings = settings or get_settings()
    target = path or settings.events_path
    if not target.exists():
        raise DatasetError(f"event dataset not found: {target}")
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    rows = raw.get("events", []) if isinstance(raw, dict) else raw
    events: list[LabeledEvent] = []
    seen: set[str] = set()
    for row in rows:
        event_id = row["id"]
        if event_id in seen:
            raise DatasetError(f"duplicate event id {event_id}")
        seen.add(event_id)
        published_at = _published_at(row["date"], row.get("time_et"))
        source = SourceRef(
            name=row.get("source_name", "curated"),
            url=row.get("source_url"),
            tier=SourceTier(row.get("source_tier", "official")),
            published_at=published_at,
        )
        magnitude = Magnitude(**row["magnitude"]) if row.get("magnitude") else None
        surprise = Surprise(**row["surprise"]) if row.get("surprise") else None
        try:
            event = LabeledEvent(
                id=event_id,
                headline=row["headline"],
                summary=row.get("summary", ""),
                published_at=published_at,
                source=source,
                event_type=EventType(row["event_type"]),
                direction=Direction(row["direction"]),
                actor=row.get("actor"),
                magnitude=magnitude,
                surprise=surprise,
                keywords=row.get("keywords", []),
                entities=row.get("entities", []),
                confidence=float(row.get("confidence", 0.95)),
                extraction_method="gold",
                gold_event_type=EventType(row.get("gold_event_type", row["event_type"])),
                gold_direction=Direction(row.get("gold_direction", row["direction"])),
                gold_magnitude=magnitude,
                gold_surprise=surprise,
                session=row.get("session", "during"),
                tags=[str(tag) for tag in row.get("tags", [])],
            )
        except (ValidationError, KeyError, ValueError) as exc:
            raise DatasetError(f"invalid event {event_id}: {exc}") from exc
        events.append(event)
    events.sort(key=lambda item: item.published_at)
    return events


def news_item(event: LabeledEvent) -> NewsItem:
    return NewsItem(
        id=event.id,
        title=event.headline,
        summary=event.summary,
        url=event.source.url,
        source_name=event.source.name,
        source_tier=event.source.tier,
        published_at=event.published_at,
    )


def split_by_date(
    events: list[LabeledEvent], train_fraction: float = 0.5
) -> tuple[list[LabeledEvent], list[LabeledEvent]]:
    ordered = sorted(events, key=lambda item: item.published_at)
    cut = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    return ordered[:cut], ordered[cut:]
