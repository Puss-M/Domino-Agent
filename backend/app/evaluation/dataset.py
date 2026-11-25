"""Dated event datasets used for extraction and event-study tests.

Three datasets are available:

- ``curated``: 50 hand-curated, heterogeneous macro events. The labels are
  editorial and the headlines are real-ish text, so this is the extraction
  benchmark.
- ``fomc``: 31 systematic FOMC target-range changes (2015-2025) generated from
  official statements. This is a homogeneous transmission benchmark; headlines
  are templated from the parsed range.
- ``extended``: curated + FOMC, deduplicated by event type and date. Curated
  events win when both describe the same decision.

Labels are assigned from the official action/consensus, not from the market
reaction. Outcomes are computed separately in ``event_study.py``.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime
from pathlib import Path
from typing import Literal
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
DatasetName = Literal["curated", "fomc", "fomc_surprise", "extended"]
DATASETS: tuple[str, ...] = ("curated", "fomc", "fomc_surprise", "extended")


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


def _load_file(target: Path) -> list[LabeledEvent]:
    if not target.exists():
        raise DatasetError(f"event dataset not found: {target}")
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    rows = raw.get("events", []) if isinstance(raw, dict) else raw
    events: list[LabeledEvent] = []
    seen: set[str] = set()
    for row in rows:
        event_id = row["id"]
        if event_id in seen:
            raise DatasetError(f"duplicate event id {event_id} in {target}")
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
    return events


def fomc_events_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / "events" / "fomc_generated.yaml"


def fomc_surprise_events_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / "events" / "fomc_surprise.yaml"


def load_events(
    path: Path | None = None,
    settings: Settings | None = None,
    dataset: DatasetName = "curated",
) -> list[LabeledEvent]:
    """Load a named dataset, or a specific file when ``path`` is given."""
    if dataset not in DATASETS:
        raise DatasetError(f"unknown dataset {dataset!r}; choose from {DATASETS}")
    settings = settings or get_settings()
    if path is not None:
        events = _load_file(path)
    elif dataset == "curated":
        events = _load_file(settings.events_path)
    elif dataset == "fomc":
        events = _load_file(fomc_events_path(settings))
    elif dataset == "fomc_surprise":
        events = _load_file(fomc_surprise_events_path(settings))
    else:
        curated = _load_file(settings.events_path)
        generated = _load_file(fomc_events_path(settings))
        # Curated wins when both files describe the same decision.
        keys = {(event.event_type, event.published_at.date()) for event in curated}
        merged = list(curated)
        for event in generated:
            key = (event.event_type, event.published_at.date())
            if key in keys:
                continue
            keys.add(key)
            merged.append(event)
        events = merged
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
