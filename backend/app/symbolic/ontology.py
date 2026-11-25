"""A small typed ontology for macro quantities and a Turtle export.

This is the "type discipline" layer: units carry dimensions, and an event's
magnitude unit must be compatible with its event type. It is deliberately
lightweight (no OWL reasoner), but it gives the symbolic layer a formal
vocabulary and produces an RDF/Turtle artifact that other tools can consume.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ..schemas import EventType, MacroEvent


class Dimension(str, Enum):
    RATE = "rate"           # bps, pp
    INFLATION = "inflation"  # pct (level), pp (surprise)
    PRICE = "price"         # usd
    QUANTITY = "quantity"   # mbpd, count
    MONEY = "money"         # usd_bn
    VOLATILITY = "volatility"
    INDEX = "index"


UNIT_DIMENSIONS: dict[str, Dimension] = {
    "bps": Dimension.RATE,
    "pp": Dimension.RATE,
    "pct": Dimension.INFLATION,
    "usd_bn": Dimension.MONEY,
    "usd": Dimension.PRICE,
    "mbpd": Dimension.QUANTITY,
    "count": Dimension.QUANTITY,
    "index": Dimension.INDEX,
    "qualitative": Dimension.INDEX,
}

EVENT_EXPECTED_DIMENSIONS: dict[EventType, set[Dimension]] = {
    EventType.MONETARY_POLICY: {Dimension.RATE},
    EventType.INFLATION: {Dimension.INFLATION, Dimension.RATE},
    EventType.LABOR_MARKET: {Dimension.QUANTITY, Dimension.RATE},
    EventType.TRADE_POLICY: {Dimension.MONEY, Dimension.RATE},
    EventType.ENERGY_SUPPLY: {Dimension.QUANTITY, Dimension.RATE},
    EventType.FISCAL_POLICY: {Dimension.MONEY, Dimension.RATE},
    EventType.CHINA_POLICY: {Dimension.RATE, Dimension.MONEY},
    EventType.GEOPOLITICS: {Dimension.INDEX, Dimension.RATE},
    EventType.FINANCIAL_STABILITY: {Dimension.MONEY, Dimension.RATE},
}


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str
    dimension: Dimension

    @classmethod
    def parse(cls, value: float, unit: str) -> "Quantity":
        return cls(value=value, unit=unit, dimension=UNIT_DIMENSIONS.get(unit, Dimension.INDEX))

    def compatible_with(self, other: "Quantity") -> bool:
        return self.dimension is other.dimension


def validate_event_units(event: MacroEvent) -> list[str]:
    """Return human-readable type violations, not exceptions."""
    issues: list[str] = []
    expected = EVENT_EXPECTED_DIMENSIONS.get(event.event_type)
    if event.magnitude and expected:
        quantity = Quantity.parse(event.magnitude.value, event.magnitude.unit)
        if quantity.dimension not in expected:
            issues.append(
                f"magnitude unit {event.magnitude.unit!r} has dimension "
                f"{quantity.dimension.value}, expected one of "
                f"{sorted(d.value for d in expected)} for {event.event_type.value}"
            )
    if event.surprise and event.surprise.unit in {"bps", "pp", "pct"}:
        quantity = Quantity.parse(event.surprise.value, event.surprise.unit)
        if event.magnitude and expected:
            anchor = Quantity.parse(event.magnitude.value, event.magnitude.unit)
            if quantity.dimension is not anchor.dimension:
                # bps and pp are both RATE, so a monetary surprise in pp is fine.
                issues.append(
                    f"surprise unit {event.surprise.unit!r} is incompatible with "
                    f"magnitude unit {event.magnitude.unit!r}"
                )
    return issues


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def to_turtle(knowledge) -> str:
    """Export channels/mechanisms as a compact RDF graph (no rdflib needed)."""
    lines = [
        "@prefix domino: <https://github.com/Puss-M/Domino-Agent/ontology#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "",
        "domino:Event a rdfs:Class .",
        "domino:Channel a rdfs:Class .",
        "domino:Mechanism a rdfs:Class .",
        "domino:Asset a rdfs:Class .",
        "",
    ]
    for channel in knowledge.channels.values():
        lines.append(f"domino:channel_{channel.id} a domino:Channel ;")
        lines.append(f'  rdfs:label "{_escape(channel.name)}" ;')
        lines.append(f'  rdfs:comment "{_escape(channel.description)}" .')
        for asset, loading in channel.loadings.items():
            sign = "positive" if loading > 0 else "negative" if loading < 0 else "zero"
            lines.append(
                f'domino:channel_{channel.id} domino:{sign}Loading domino:asset_{re.sub(r"[^A-Za-z0-9]", "_", asset)} .'
            )
        for citation in channel.citations:
            lines.append(f'domino:channel_{channel.id} dct:source "{_escape(citation)}" .')
        lines.append("")
    for mechanism in knowledge.mechanisms:
        lines.append(f"domino:mechanism_{mechanism.id} a domino:Mechanism ;")
        lines.append(f'  rdfs:label "{_escape(mechanism.title)}" ;')
        lines.append(f'  domino:evidenceGrade "{mechanism.evidence_grade.value}" ;')
        lines.append(f"  domino:confidence {mechanism.confidence} ;")
        for channel_id in mechanism.channels:
            lines.append(
                f"  domino:activates domino:channel_{channel_id} ;"
            )
        for citation in mechanism.citations:
            lines.append(f'  dct:source "{_escape(citation)}" ;')
        lines.append(f'  rdfs:comment "{_escape(mechanism.rationale)}" .')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
