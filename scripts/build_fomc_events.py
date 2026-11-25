"""Build the systematic FOMC benchmark from official statements.

The statements snapshot is in `backend/data/fomc/statements_2000_2025.csv`.
The script parses the target range from each statement, computes the change
versus the previous meeting, and emits a dated event YAML for non-zero changes.

Why this exists: the curated 50-event sample is heterogeneous and hand-built.
This builder produces a homogeneous, reproducible FOMC rate-change benchmark
that can be evaluated separately or merged with the curated sample.

Usage:
    python scripts/build_fomc_events.py
"""

from __future__ import annotations

import re
import sys
from datetime import date, time
from fractions import Fraction
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import ftfy
except ImportError:  # pragma: no cover - the generated file is committed
    ftfy = None


DASHES = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2212]")
RANGE_AFTER = re.compile(
    r"target range for the federal funds rate.{0,180}?([0-9][0-9\s\-/]*)\s+to\s+([0-9][0-9\s\-/]*)\s+percent",
    re.IGNORECASE,
)
RANGE_BEFORE = re.compile(
    r"([0-9][0-9\s\-/]*)\s+to\s+([0-9][0-9\s\-/]*)\s+percent target range for the federal funds rate",
    re.IGNORECASE,
)
SINGLE = re.compile(
    r"target for the federal funds rate.{0,80}?([0-9][0-9\s\-/]*)\s+percent",
    re.IGNORECASE,
)
RELEASE = re.compile(r"For release at (\d{1,2}):(\d{2}) (a\.m\.|p\.m\.) (EST|EDT)", re.IGNORECASE)


def normalize(text: str) -> str:
    value = ftfy.fix_text(str(text)) if ftfy else str(text)
    value = value.replace("\r", " ")
    value = DASHES.sub("-", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_fraction(value: str) -> float:
    value = value.strip().replace(" ", "")
    if "-" in value and "/" in value:
        whole, fraction = value.split("-", 1)
        return float(whole) + float(Fraction(fraction))
    if "/" in value:
        return float(Fraction(value))
    return float(value)


def parse_range(text: str) -> tuple[float, float] | None:
    for pattern in (RANGE_AFTER, RANGE_BEFORE):
        match = pattern.search(text)
        if match:
            return parse_fraction(match.group(1)), parse_fraction(match.group(2))
    match = SINGLE.search(text)
    if match:
        value = parse_fraction(match.group(1))
        return value, value
    return None


def parse_release(text: str) -> tuple[time, str]:
    match = RELEASE.search(text)
    if not match:
        return time(14, 0), "during"
    hour, minute = int(match.group(1)), int(match.group(2))
    if match.group(3).lower().startswith("p") and hour != 12:
        hour += 12
    if match.group(3).lower().startswith("a") and hour == 12:
        hour = 0
    release = time(hour, minute)
    if release < time(9, 30):
        session = "before_open"
    elif release > time(16, 0):
        session = "after_close"
    else:
        session = "during"
    return release, session


def date_from_url(url: str, fallback: date) -> date:
    match = re.search(r"monetary(\d{8})", url) or re.search(r"/(\d{8})[a-z]?\.htm", url)
    if not match:
        return fallback
    raw = match.group(1)
    parsed = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    # Only trust the URL date when it is close to the scraped meeting date;
    # otherwise a stray 8-digit token could move the event.
    if abs((parsed - fallback).days) > 5:
        return fallback
    return parsed


def main() -> None:
    source_path = ROOT / "backend" / "data" / "fomc" / "statements_2000_2025.csv"
    output_path = ROOT / "backend" / "data" / "events" / "fomc_generated.yaml"
    frame = pd.read_csv(source_path)
    frame["meeting_date"] = pd.to_datetime(frame["meeting_date"])
    frame = frame[frame["meeting_date"] >= "2004-06-01"].sort_values("meeting_date")

    # The 2000-2003 statements use inconsistent single-value phrasings and
    # produce parsing artefacts; the systematic benchmark starts with the
    # 2004-2006 hiking cycle.
    previous_upper = 1.0  # target on 2004-06-29, before the 2004-06-30 hike
    events = []
    for _, row in frame.iterrows():
        text = normalize(row["text"])
        parsed = parse_range(text)
        if parsed is None:
            continue
        lower, upper = parsed
        event_date = date_from_url(str(row["source_url"]), row["meeting_date"].date())
        delta = round((upper - previous_upper) * 100)
        previous_upper = upper
        if delta == 0:
            continue
        if abs(delta) not in {25, 50, 75, 100}:
            # Guard against parsing a stray "2 percent inflation" figure as a
            # target-rate change.
            continue
        release_time, session = parse_release(text)
        direction = "tightening" if delta > 0 else "easing"
        action = "raises" if delta > 0 else "cuts"
        target = (
            f"{lower:.2f}%"
            if abs(lower - upper) < 1e-9
            else f"{lower:.2f}%-{upper:.2f}%"
        )
        headline = f"Fed {action} rates by {abs(delta)} basis points to {target}"
        decided = re.search(r"The Committee decided to .{0,220}?percent", text)
        summary = decided.group(0) if decided else text[:260]
        events.append(
            {
                "id": f"fomc-stmt-{event_date.isoformat()}",
                "date": event_date.isoformat(),
                "time_et": release_time.strftime("%H:%M"),
                "session": session,
                "event_type": "monetary_policy",
                "direction": direction,
                "actor": "US_FED",
                "headline": headline,
                "summary": summary,
                "source_name": "Federal Reserve",
                "source_url": str(row["source_url"]),
                "source_tier": "official",
                "magnitude": {"value": abs(delta), "unit": "bps"},
                "surprise": {"value": 0, "unit": "qualitative", "sign": "neutral"},
                "tags": ["fomc", "statement", "generated"],
            }
        )

    payload = {
        "version": 1,
        "notes": [
            "Generated by scripts/build_fomc_events.py from official FOMC statements.",
            "Only non-zero target-range changes are included; holds are omitted.",
            "Headlines are templated from the parsed target range; summaries are statement excerpts.",
            "Surprise is neutral because no high-frequency consensus series is bundled.",
        ],
        "events": events,
    }
    output_path.write_text(
        "# Generated file. Do not edit by hand; run scripts/build_fomc_events.py.\n"
        + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"wrote {len(events)} events to {output_path}")
    for event in events:
        print(event["date"], event["direction"], event["magnitude"]["value"], event["headline"])


if __name__ == "__main__":
    main()
