"""Entity normalisation for macro headlines.

A headline says "the Fed", "FOMC" or "美联储"; the mechanism library needs one
canonical key. This module is deliberately a controlled vocabulary rather than
a general NER model: the vocabulary *is* the coverage boundary, and anything
outside it is reported as unmatched instead of being silently linked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENTITY_ALIASES: dict[str, list[str]] = {
    "US_FED": ["federal reserve", "the fed", "fed", "fomc", "美联储", "联储"],
    "ECB": ["european central bank", "ecb", "欧洲央行"],
    "BOJ": ["bank of japan", "boj", "日本央行"],
    "PBOC": ["people's bank of china", "pboc", "中国人民银行", "中国央行", "央行"],
    "US_GOV": ["white house", "us government", "u.s. government", "congress", "administration", "美国政府", "白宫"],
    "CHINA_GOV": ["chinese government", "beijing", "state council", "中国政府", "国务院"],
    "OPEC_PLUS": ["opec+", "opec plus", "opec", "欧佩克", "石油输出国组织"],
    "US_EQUITIES": ["s&p 500", "s&p", "wall street", "us stocks", "u.s. stocks", "美股"],
    "TECH": ["tech stocks", "technology stocks", "nasdaq", "科技股", "纳斯达克"],
    "ENERGY": ["crude oil", "brent", "wti", "oil prices", "oil", "原油", "油价", "石油"],
    "GOLD": ["gold", "黄金"],
    "USD": ["us dollar", "dollar", "dxy", "美元"],
    "TREASURIES": ["treasuries", "treasury bonds", "long bonds", "bonds", "美债", "国债"],
    "EM": ["emerging markets", "emerging market", "em equities", "新兴市场"],
    "CHINA_EQUITIES": ["china stocks", "chinese stocks", "a-shares", "hong kong stocks", "中概股", "a股", "港股"],
    "CREDIT": ["high yield", "credit spreads", "junk bonds", "高收益债", "信用利差"],
}

_ASSET_MAP = {
    "US_EQUITIES": ["SPY"],
    "TECH": ["QQQ"],
    "ENERGY": ["XLE"],
    "GOLD": ["GLD"],
    "USD": ["UUP"],
    "TREASURIES": ["TLT", "IEF"],
    "EM": ["EEM"],
    "CHINA_EQUITIES": ["FXI"],
    "CREDIT": ["HYG"],
}

_ACTORS = {"US_FED", "ECB", "BOJ", "PBOC", "US_GOV", "CHINA_GOV", "OPEC_PLUS"}


@dataclass(frozen=True)
class EntityMatch:
    canonical: str
    alias: str
    start: int
    end: int


def _compile(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if re.search(r"[\u4e00-\u9fff]", alias):
        return re.compile(escaped, re.IGNORECASE)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


_COMPILED: list[tuple[str, str, re.Pattern[str]]] = sorted(
    (
        (canonical, alias, _compile(alias))
        for canonical, aliases in ENTITY_ALIASES.items()
        for alias in aliases
    ),
    key=lambda item: len(item[1]),
    reverse=True,
)


def normalize_entities(text: str) -> list[EntityMatch]:
    matches: list[EntityMatch] = []
    occupied: list[tuple[int, int]] = []
    for canonical, alias, pattern in _COMPILED:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(span[0] < end and span[1] > start for start, end in occupied):
                continue
            occupied.append(span)
            matches.append(
                EntityMatch(canonical=canonical, alias=alias, start=span[0], end=span[1])
            )
    return sorted(matches, key=lambda item: item.start)


def entity_names(text: str) -> list[str]:
    seen: list[str] = []
    for match in normalize_entities(text):
        if match.canonical not in seen:
            seen.append(match.canonical)
    return seen


def actor(text: str) -> str | None:
    for match in normalize_entities(text):
        if match.canonical in _ACTORS:
            return match.canonical
    return None


def assets_for_text(text: str) -> list[str]:
    assets: list[str] = []
    for canonical in entity_names(text):
        for ticker in _ASSET_MAP.get(canonical, []):
            if ticker not in assets:
                assets.append(ticker)
    return assets
