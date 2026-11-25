"""Load and validate the transmission library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..schemas import ChannelSpec, EvidenceGrade, MechanismSpec


class KnowledgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeBase:
    version: int
    channels: dict[str, ChannelSpec]
    mechanisms: list[MechanismSpec]
    path: Path

    @property
    def assets(self) -> list[str]:
        assets: set[str] = set()
        for channel in self.channels.values():
            assets.update(channel.loadings)
        return sorted(assets)


def load_knowledge(path: Path | None = None, settings: Settings | None = None) -> KnowledgeBase:
    settings = settings or get_settings()
    target = path or settings.mechanisms_path
    if not target.exists():
        raise KnowledgeError(f"knowledge base not found: {target}")
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise KnowledgeError(f"invalid YAML in {target}: {exc}") from exc
    if not isinstance(raw, dict) or "channels" not in raw or "mechanisms" not in raw:
        raise KnowledgeError("knowledge base must contain 'channels' and 'mechanisms'")

    channels: dict[str, ChannelSpec] = {}
    for item in raw["channels"]:
        try:
            channel = ChannelSpec(**item)
        except ValidationError as exc:
            raise KnowledgeError(f"invalid channel {item.get('id')}: {exc}") from exc
        if channel.id in channels:
            raise KnowledgeError(f"duplicate channel id {channel.id}")
        if not channel.citations:
            raise KnowledgeError(f"channel {channel.id} has no citations")
        channels[channel.id] = channel

    mechanisms: list[MechanismSpec] = []
    seen: set[str] = set()
    for item in raw["mechanisms"]:
        try:
            mechanism = MechanismSpec(**item)
        except ValidationError as exc:
            raise KnowledgeError(f"invalid mechanism {item.get('id')}: {exc}") from exc
        if mechanism.id in seen:
            raise KnowledgeError(f"duplicate mechanism id {mechanism.id}")
        seen.add(mechanism.id)
        if not mechanism.citations:
            raise KnowledgeError(f"mechanism {mechanism.id} has no citations")
        for channel_id in mechanism.channels:
            if channel_id not in channels:
                raise KnowledgeError(
                    f"mechanism {mechanism.id} references unknown channel {channel_id}"
                )
        if mechanism.evidence_grade == EvidenceGrade.A and not mechanism.rationale:
            raise KnowledgeError(f"grade-A mechanism {mechanism.id} needs a rationale")
        mechanisms.append(mechanism)

    return KnowledgeBase(
        version=int(raw.get("version", 1)),
        channels=channels,
        mechanisms=mechanisms,
        path=target,
    )
