"""Point-in-time contract for benchmark inputs.

The benchmark cannot be a live vintage database without an archive of every
source. What it can do is declare, per source, when a value became public and
whether the snapshot is revised. This turns "we used adjusted closes" from a
footnote into an auditable check.

The contract is deliberately conservative: a source is only `point_in_time` if
the project actually stores a vintage. Yahoo adjusted closes, editorial labels
and the ex-post Bu-Rogers-Wu series are not vintages, so the verdict is
"not_point_in_time" even though the LLM-free metric path has no parametric
lookahead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from ..config import Settings, get_settings
from ..schemas import LabeledEvent

_MANIFEST_NAME = "point_in_time.yaml"


@dataclass(frozen=True)
class SourceAvailability:
    id: str
    name: str
    fields: tuple[str, ...]
    available_at: str
    revision: str
    point_in_time: str
    used_in_benchmark: bool
    datasets: tuple[str, ...]
    caveat: str

    @classmethod
    def from_dict(cls, payload: dict) -> "SourceAvailability":
        return cls(
            id=str(payload["id"]),
            name=str(payload["name"]),
            fields=tuple(str(field) for field in payload.get("fields", [])),
            available_at=str(payload.get("available_at", "")),
            revision=str(payload.get("revision", "")),
            point_in_time=str(payload.get("point_in_time", "no")),
            used_in_benchmark=bool(payload.get("used_in_benchmark", False)),
            datasets=tuple(str(item) for item in payload.get("datasets", [])),
            caveat=str(payload.get("caveat", "")),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "fields": list(self.fields),
            "available_at": self.available_at,
            "revision": self.revision,
            "point_in_time": self.point_in_time,
            "used_in_benchmark": self.used_in_benchmark,
            "datasets": list(self.datasets),
            "caveat": self.caveat,
        }


def load_point_in_time(
    path: Path | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    path = path or (settings.data_dir / _MANIFEST_NAME)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "sources" not in payload:
        raise ValueError(f"invalid point-in-time manifest: {path}")
    return payload


def _is_revised(source: SourceAvailability) -> bool:
    if source.point_in_time in {"no", "editorial", "ex_post"}:
        return True
    revision = source.revision.lower()
    return "revis" in revision or "can be updated" in revision


def audit_point_in_time(
    events: list[LabeledEvent],
    dataset: str,
    *,
    price_last_date: date | None = None,
    path: Path | None = None,
    settings: Settings | None = None,
) -> dict:
    manifest = load_point_in_time(path=path, settings=settings)
    sources = [SourceAvailability.from_dict(item) for item in manifest["sources"]]
    used = [
        source
        for source in sources
        if source.used_in_benchmark
        and (not source.datasets or dataset in source.datasets)
    ]
    revised = [source.id for source in used if _is_revised(source)]
    event_dates = sorted(event.published_at.date() for event in events)

    checks = [
        {
            "id": "no_llm_metric_path",
            "passed": True,
            "detail": "Rules, mechanism retrieval, sign algebra and the event study are deterministic; no LLM sits in the metric path.",
        },
        {
            "id": "event_timestamps_present",
            "passed": all(event.published_at for event in events),
            "detail": f"{len(events)} events carry an editorial published_at timestamp.",
        },
        {
            "id": "labels_frozen",
            "passed": False,
            "detail": "Curated labels are hand-edited; they are not a frozen third-party dataset.",
        },
        {
            "id": "prices_point_in_time",
            "passed": False,
            "detail": "Yahoo adjusted closes are retroactively adjusted for splits and dividends.",
        },
        {
            "id": "surprises_point_in_time",
            "passed": False,
            "detail": "The Bu-Rogers-Wu series is an ex-post published series, not a real-time feed.",
        },
    ]
    if price_last_date is not None:
        checks.append(
            {
                "id": "events_within_price_snapshot",
                "passed": not event_dates or max(event_dates) <= price_last_date,
                "detail": (
                    f"Latest event {max(event_dates).isoformat() if event_dates else 'n/a'}; "
                    f"price snapshot ends {price_last_date.isoformat()}."
                ),
            }
        )

    return {
        "dataset": dataset,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": manifest.get("as_of"),
        "n_events": len(events),
        "event_window": {
            "start": event_dates[0].isoformat() if event_dates else None,
            "end": event_dates[-1].isoformat() if event_dates else None,
        },
        "llm_in_metric_path": False,
        "used_sources": [source.id for source in used],
        "revised_sources": revised,
        "sources": [source.to_dict() for source in sources],
        "checks": checks,
        "verdict": "not_point_in_time" if revised else "point_in_time",
        "summary": (
            "The LLM-free metric path removes parametric lookahead, but the "
            "benchmark is not a point-in-time reconstruction: "
            + ", ".join(revised)
            + " are revised or ex-post."
            if revised
            else "Every benchmark input is a point-in-time vintage."
        ),
    }
