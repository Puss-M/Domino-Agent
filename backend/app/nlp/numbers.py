"""Financial number and surprise parsing.

The goal is not general NLP. It is to recover the handful of quantities that
actually move an event study: policy-rate changes in basis points, inflation
surprises in percentage points, traded-commodity volumes, and fiscal/trade
amounts in USD. Units are normalised once, at the boundary, so downstream code
never has to guess whether "50" means 50bp or 50%.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import Magnitude, Surprise

_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"

_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "bps",
        re.compile(rf"({_NUM})\s*(?:bps?|basis\s+points?|个?基点)", re.IGNORECASE),
        1.0,
    ),
    (
        "pp",
        re.compile(rf"({_NUM})\s*(?:percentage\s+points?|ppt|pp|个百分点)", re.IGNORECASE),
        1.0,
    ),
    (
        "pct",
        re.compile(rf"({_NUM})\s*(?:%|percent|per\s+cent|pct|％)", re.IGNORECASE),
        1.0,
    ),
    (
        "usd_tn",
        re.compile(
            rf"(?:\$|USD\s*|US\$)\s*({_NUM})\s*(trillion|tn|t\b|万亿美元)",
            re.IGNORECASE,
        ),
        1.0,
    ),
    (
        "usd_bn",
        re.compile(
            rf"(?:\$|USD\s*|US\$)\s*({_NUM})\s*(billion|bn|b\b|亿美元|十亿美元)",
            re.IGNORECASE,
        ),
        1.0,
    ),
    (
        "usd_mn",
        re.compile(
            rf"(?:\$|USD\s*|US\$)\s*({_NUM})\s*(million|mn|m\b|百万美元)",
            re.IGNORECASE,
        ),
        1.0,
    ),
    (
        "usd",
        re.compile(rf"(?:\$|USD\s*)\s*({_NUM})(?!\s*(?:billion|bn|million|mn|b\b|m\b))", re.IGNORECASE),
        1.0,
    ),
    (
        "mbpd",
        re.compile(
            rf"({_NUM})\s*(?:million\s+barrels?\s+(?:a|per)\s+day|mb/?d|mbpd|百万桶/日|万桶/日)",
            re.IGNORECASE,
        ),
        1.0,
    ),
    (
        "count",
        re.compile(
            rf"(?:payrolls|jobs)\s+(?:rise|rises|rose|increase|increased|fall|falls|fell|decline|declined)\s+(?:by\s+)?({_NUM})",
            re.IGNORECASE,
        ),
        1.0,
    ),
    (
        "count",
        re.compile(
            rf"(?:by|added|adds|rose\s+by|rise\s+by|rises\s+by|fell\s+by)\s+({_NUM})\s*(?:jobs|payrolls|positions)",
            re.IGNORECASE,
        ),
        1.0,
    ),
]

_CN_UNIT_SCALE = {"亿美元": 0.1, "十亿美元": 1.0, "百万美元": 0.001, "万桶/日": 0.01}


@dataclass(frozen=True)
class ParsedNumber:
    value: float
    unit: str
    raw: str
    start: int
    end: int

    def as_dict(self) -> dict:
        return {"value": self.value, "unit": self.unit, "raw": self.raw}


def parse_numbers(text: str) -> list[ParsedNumber]:
    """Return unit-bearing numbers, de-duplicated by span, longest match first."""
    matches: list[ParsedNumber] = []
    for unit, pattern, _scale in _PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0).strip()
            number = float(match.group(1).replace(",", ""))
            normalized_unit = unit
            value = number
            if unit == "usd_bn":
                if "亿" in raw:
                    value = number * _CN_UNIT_SCALE["亿美元"]
                elif "十亿" in raw:
                    value = number
            elif unit == "usd_tn":
                value = number * 1000.0
                normalized_unit = "usd_bn"
            elif unit == "usd_mn":
                value = number / 1000.0
                normalized_unit = "usd_bn"
            elif unit == "mbpd":
                if "万桶" in raw:
                    value = number * _CN_UNIT_SCALE["万桶/日"]
            matches.append(
                ParsedNumber(
                    value=value,
                    unit=normalized_unit,
                    raw=raw,
                    start=match.start(),
                    end=match.end(),
                )
            )
    # Prefer the longest match at a given start, then remove overlaps.
    matches.sort(key=lambda item: (item.start, -(item.end - item.start)))
    kept: list[ParsedNumber] = []
    for item in matches:
        if kept and item.start < kept[-1].end:
            continue
        kept.append(item)
    return kept


def best_magnitude(text: str, event_type: str) -> Magnitude | None:
    parsed = parse_numbers(text)
    if not parsed:
        return None
    preference = {
        "monetary_policy": ["bps", "pp", "pct", "usd_bn", "mbpd"],
        "inflation": ["pp", "pct", "bps"],
        "labor_market": ["count", "pct", "pp"],
        "trade_policy": ["usd_bn", "pct", "pp"],
        "energy_supply": ["mbpd", "pct", "usd_bn"],
        "fiscal_policy": ["usd_bn", "pct", "pp"],
        "china_policy": ["bps", "pct", "usd_bn"],
        "geopolitics": ["pct", "usd_bn", "mbpd"],
        "financial_stability": ["usd_bn", "pct", "bps"],
    }.get(event_type, ["pct", "pp", "bps", "usd_bn", "mbpd"])
    by_unit: dict[str, ParsedNumber] = {}
    for item in parsed:
        by_unit.setdefault(item.unit, item)  # first mention is the headline number
    for unit in preference:
        if unit in by_unit:
            item = by_unit[unit]
            return Magnitude(value=round(item.value, 4), unit=item.unit, raw=item.raw)
    item = parsed[0]
    unit = item.unit if item.unit in {"bps", "pp", "pct", "usd_bn", "usd", "mbpd"} else "qualitative"
    return Magnitude(value=round(item.value, 4), unit=unit, raw=item.raw)


_HOT = [
    "more than expected",
    "hotter than expected",
    "higher than expected",
    "above expectations",
    "above consensus",
    "larger than expected",
    "beat expectations",
    "unexpectedly strong",
    "surprise hike",
    "surprise increase",
    "超预期",
    "高于预期",
    "意外加息",
]
_COOL = [
    "less than expected",
    "cooler than expected",
    "lower than expected",
    "below expectations",
    "below consensus",
    "smaller than expected",
    "missed expectations",
    "unexpectedly weak",
    "surprise cut",
    "surprise decline",
    "低于预期",
    "不及预期",
    "意外降息",
]
_INLINE = ["as expected", "in line", "inline", "unchanged expectations", "符合预期"]


def detect_surprise(text: str) -> Surprise:
    lowered = text.lower()
    for phrase in _INLINE:
        if phrase in lowered:
            return Surprise(value=0.0, unit="qualitative", sign="neutral", raw=phrase)
    sign = "neutral"
    raw = ""
    for phrase in _HOT:
        if phrase in lowered:
            sign, raw = "positive", phrase
            break
    if sign == "neutral":
        for phrase in _COOL:
            if phrase in lowered:
                sign, raw = "positive", phrase  # "more easing/less inflation than priced"
                break
    value = 0.0
    unit = "qualitative"
    # "8.6% vs 8.3% expected" -> +0.3pp
    vs = re.search(
        rf"({_NUM})\s*(%|percent)?\s*(?:vs\.?|versus|against|compared\s+with)\s*"
        rf"({_NUM})\s*(%|percent)?\s*(?:expected|consensus)",
        text,
        re.IGNORECASE,
    )
    if vs:
        actual = float(vs.group(1).replace(",", ""))
        expected = float(vs.group(3).replace(",", ""))
        value = round(actual - expected, 4)
        unit = "pp" if (vs.group(2) or vs.group(4)) else "qualitative"
        sign = "positive" if value > 0 else "negative" if value < 0 else "neutral"
        raw = vs.group(0)
    return Surprise(value=value, unit=unit, sign=sign, raw=raw)


def surprise_scale(event_type: str, surprise: Surprise | None, magnitude: Magnitude | None) -> float:
    """Map an event's size to a multiplier around 1.0 for transmission strengths."""
    if surprise and surprise.value:
        if surprise.unit == "bps":
            return max(0.5, min(2.0, abs(surprise.value) / 25.0))
        if surprise.unit == "pp":
            return max(0.5, min(2.0, abs(surprise.value) / 0.2))
    if magnitude:
        if magnitude.unit == "count":
            return max(0.5, min(2.0, abs(magnitude.value) / 150000.0))
        if magnitude.unit == "bps":
            return max(0.5, min(2.0, abs(magnitude.value) / 25.0))
        if magnitude.unit == "pp":
            return max(0.5, min(2.0, abs(magnitude.value) / 0.2))
        if magnitude.unit == "mbpd":
            return max(0.5, min(2.0, abs(magnitude.value) / 1.0))
        if magnitude.unit == "usd_bn":
            return max(0.5, min(2.0, abs(magnitude.value) / 100.0))
    return 1.0
