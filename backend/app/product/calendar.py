"""Macro calendar for the Audit Desk.

The seed is deliberately small and sourced: FOMC decisions from the Federal
Reserve and BEA releases from the BEA schedule. Custom events are stored in
SQLite by the product layer. This is not a complete economic calendar; it is the
forward-looking surface the workflow needs.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from ..config import Settings, get_settings

_CALENDAR_NAME = "calendar.yaml"


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_calendar(
    settings: Settings | None = None,
    store=None,
    path: Path | None = None,
) -> list[dict]:
    settings = settings or get_settings()
    path = path or (settings.data_dir / "calendar" / _CALENDAR_NAME)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    events = []
    for item in payload.get("events", []):
        entry = dict(item)
        entry["date"] = _parse_date(entry["date"]).isoformat()
        entry["custom"] = False
        events.append(entry)
    if store is not None:
        for item in store.list_custom_calendar():
            entry = dict(item)
            entry["date"] = _parse_date(entry["date"]).isoformat()
            entry["custom"] = True
            events.append(entry)
    return sorted(events, key=lambda item: (item["date"], item.get("time", "")))


def calendar_window(
    days: int = 45,
    include_past: int = 7,
    settings: Settings | None = None,
    store=None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    start = today.fromordinal(today.toordinal() - include_past)
    end = today.fromordinal(today.toordinal() + days)
    events = []
    for item in load_calendar(settings=settings, store=store):
        event_date = _parse_date(item["date"])
        if not (start <= event_date <= end):
            continue
        entry = dict(item)
        entry["days_until"] = (event_date - today).days
        entry["is_past"] = event_date < today
        events.append(entry)
    return {
        "as_of": today.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "events": events,
        "n_events": len(events),
        "sources": {
            "fed": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            "bea": "https://www.bea.gov/news/schedule",
        },
    }


def find_calendar_event(
    event_id: str,
    settings: Settings | None = None,
    store=None,
) -> dict:
    for item in load_calendar(settings=settings, store=store):
        if item["id"] == event_id:
            return item
    raise KeyError(event_id)


def calendar_payload(item: dict) -> dict:
    """Map a calendar entry to the analysis engine's headline/summary input."""
    return {
        "headline": item["title"],
        "summary": item.get("summary", ""),
        "event_id": item["id"],
        "session": item.get("session", "during"),
        "published_at": item["date"],
        "source_name": item.get("source", "calendar"),
        "source_url": item.get("url", ""),
    }
