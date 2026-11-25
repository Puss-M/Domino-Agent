"""Rule-first event extraction.

Why rules before an LLM:
- the mapping from "50bp" to a policy surprise must be exact and testable;
- the same headline must produce the same event every run;
- an LLM can be added as a *fallback* for recall, but it may not overwrite a
  number that a deterministic parser already read.

The extractor returns a typed `MacroEvent` plus a debug payload with the
keyword evidence behind each decision, so an analyst can audit the pipeline.
"""

from __future__ import annotations

import hashlib
import re
from datetime import timezone

from ..schemas import (
    Direction,
    EventType,
    MacroEvent,
    NewsItem,
    SourceRef,
    SourceTier,
    Surprise,
)
from . import entities
from .numbers import best_magnitude, detect_surprise
from .sentiment import FinancialSentiment

TYPE_KEYWORDS: dict[EventType, dict[str, float]] = {
    EventType.MONETARY_POLICY: {
        "federal reserve": 3.0, "the fed": 2.5, "fed": 1.8, "fomc": 3.0, "ecb": 3.0,
        "bank of japan": 3.0, "boj": 3.0, "pboc": 2.4, "central bank": 2.0,
        "interest rate": 2.6, "rate hike": 3.0, "rate cut": 3.0, "policy rate": 2.4,
        "holds rates": 3.0, "keeps rates": 3.0, "rates steady": 2.8, "held rates": 3.0,
        "basis points": 2.0, "target range": 2.2, "monetary policy": 2.6,
        "加息": 3.0, "降息": 3.0, "利率": 2.4, "美联储": 3.0, "央行": 1.8,
    },
    EventType.INFLATION: {
        "cpi": 3.0, "consumer price": 3.0, "inflation": 2.6, "pce": 2.6,
        "price index": 2.2, "deflation": 2.4, "disinflation": 2.6,
        "通胀": 2.6, "物价": 2.2,
    },
    EventType.LABOR_MARKET: {
        "payrolls": 3.0, "nonfarm": 3.0, "non-farm": 3.0, "unemployment": 2.4,
        "jobs report": 3.0, "jobless claims": 2.6, "labor market": 2.2,
        "非农": 3.0, "失业率": 2.4, "就业": 2.0,
    },
    EventType.TRADE_POLICY: {
        "tariff": 3.2, "tariffs": 3.2, "trade war": 3.4, "section 301": 3.2,
        "export control": 2.8, "import duty": 2.8, "wto": 2.0, "trade deal": 2.6,
        "关税": 3.2, "贸易战": 3.4, "出口管制": 2.8,
    },
    EventType.ENERGY_SUPPLY: {
        "opec": 3.4, "opec+": 3.4, "oil production": 3.0, "barrels per day": 2.8,
        "crude supply": 2.8, "pipeline": 2.0, "strategic petroleum reserve": 2.8,
        "欧佩克": 3.4, "石油产量": 3.0, "原油": 2.2, "减产": 2.8,
    },
    EventType.GEOPOLITICS: {
        "war": 2.6, "invasion": 3.2, "invade": 3.2, "invades": 3.2, "invaded": 3.2,
        "military strike": 3.0, "missile": 2.4, "attack": 1.8, "attacks": 1.8,
        "sanctions": 2.6, "conflict": 2.2, "ceasefire": 3.0,
        "hamas": 3.2, "gaza": 3.0, "israel": 1.6, "iran": 1.6, "hezbollah": 2.6,
        "战争": 2.6, "入侵": 3.2, "袭击": 2.4, "制裁": 2.6, "冲突": 2.2, "停火": 3.0,
    },
    EventType.FINANCIAL_STABILITY: {
        "bank failure": 3.4, "bank run": 3.4, "bank collapse": 3.4, "banking crisis": 3.3,
        "credit crunch": 3.2, "bailout": 3.0, "emergency lending": 3.0, "svb": 3.2,
        "silicon valley bank": 3.2, "signature bank": 3.0, "contagion": 3.2,
        "financial stability": 3.0, "regulators seize": 3.0, "credit suisse": 3.2, "bank stress": 3.0,
        "银行倒闭": 3.4, "挤兑": 3.4, "救助": 3.0,
    },
    EventType.FISCAL_POLICY: {
        "fiscal stimulus": 3.4, "budget": 2.2, "spending package": 2.8, "debt ceiling": 3.0,
        "tax cut": 3.0, "tax increase": 2.8, "rescue plan": 3.2, "stimulus bill": 3.2,
        "infrastructure bill": 3.0, "财政刺激": 3.4, "预算": 2.2,
        "债务上限": 3.0, "减税": 3.0,
    },
    EventType.CHINA_POLICY: {
        "reserve requirement": 3.2, "rrr cut": 3.4, "china stimulus": 3.6, "stamp duty": 3.2,
        "pboc": 2.6, "降准": 3.4, "中国刺激": 3.6, "印花税": 3.2, "中国人民银行": 2.6,
    },
}

_DIRECTION_TERMS = {
    "tighten": ["hike", "hikes", "raise", "raises", "raised", "increase", "tighten", "tightening", "hawkish", "restrictive", "higher for longer", "加息", "上调", "收紧", "鹰派"],
    "ease": ["cut", "cuts", "lower", "lowers", "reduce", "reduces", "ease", "easing", "dovish", "降息", "下调", "宽松", "鸽派"],
    "hold": ["hold", "holds", "held", "unchanged", "pause", "维持", "不变"],
    "upside": ["hotter", "higher than expected", "above expectations", "above consensus", "accelerate", "accelerating", "rise", "rises", "surge", "beat", "beats", "beating", "超预期", "高于预期", "上涨", "加速"],
    "downside": ["cooler", "lower than expected", "below expectations", "below consensus", "decelerate", "decelerating", "fall", "falls", "decline", "miss", "misses", "missed", "weaker", "低于预期", "不及预期", "回落", "下降"],
    "escalation": ["impose", "imposes", "imposed", "raise tariffs", "new tariffs", "tariffs on", "take effect", "effective", "escalate", "escalation", "加征", "升级", "制裁"],
    "deescalation": ["pause", "exempt", "exemption", "rollback", "reduce tariffs", "truce", "de-escalate", "暂停", "豁免", "下调关税", "和谈"],
    "supply_cut": ["production cut", "production cuts", "cut oil production", "cuts oil production", "cuts output", "output cut", "reduce output", "withhold", "extend cuts", "extends cuts", "减产", "削减产量"],
    "supply_increase": ["increase output", "raise output", "add barrels", "增产", "提高产量"],
    "risk_off": ["war", "invasion", "invade", "invades", "invaded", "attack", "attacks", "strike", "escalation", "战争", "入侵", "袭击", "升级"],
    "risk_on": ["ceasefire", "truce", "peace", "de-escalation", "停火", "和谈", "和平"],
    "stimulus": ["stimulus", "stimulus package", "spending", "tax cut", "support", "stimulate", "rrr cut", "reserve requirement ratio", "signs", "passes", "rescue plan", "降准", "刺激", "减税", "支持"],
    "stress": ["failure", "run", "crunch", "crisis", "collapse", "contagion", "倒闭", "挤兑", "危机", "崩溃"],
}


def _find_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for term in terms:
        if re.search(r"[\u4e00-\u9fff]", term):
            if term in lowered:
                found.append(term)
        elif re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered):
            found.append(term)
    return found


def _earliest_position(text: str, terms: list[str]) -> int | None:
    lowered = text.lower()
    positions = []
    for term in terms:
        index = lowered.find(term)
        if index >= 0:
            positions.append(index)
    return min(positions) if positions else None


def classify_event_type(text: str) -> tuple[EventType, dict[str, float], list[str]]:
    lowered = text.lower()
    scores: dict[EventType, float] = {}
    evidence: dict[EventType, list[str]] = {}
    for event_type, keywords in TYPE_KEYWORDS.items():
        score = 0.0
        hits: list[str] = []
        for keyword, weight in keywords.items():
            pattern = re.escape(keyword)
            if re.search(r"[\u4e00-\u9fff]", keyword):
                count = lowered.count(keyword)
            else:
                count = len(re.findall(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", lowered))
            if count:
                score += weight * min(count, 2)
                hits.append(keyword)
        scores[event_type] = round(score, 3)
        evidence[event_type] = hits
    # "China unveils stimulus" / "PBOC cuts RRR" should route to the China
    # policy mechanism, not generic fiscal stimulus.
    china_terms = ["china", "chinese", "pboc", "中国", "中国人民银行"]
    stimulus_terms = ["stimulus", "rrr", "reserve requirement", "降准", "刺激", "stamp duty", "印花税"]
    if any(term in lowered for term in china_terms) and any(term in lowered for term in stimulus_terms):
        scores[EventType.CHINA_POLICY] = round(scores.get(EventType.CHINA_POLICY, 0.0) + 3.0, 3)
        evidence.setdefault(EventType.CHINA_POLICY, []).append("china+stimulus")
    best = max(scores, key=scores.get) if scores else EventType.OTHER
    if scores.get(best, 0.0) <= 0:
        best = EventType.OTHER
    return best, scores, evidence.get(best, [])


def classify_direction(text: str, event_type: EventType) -> tuple[Direction, list[str]]:
    lowered = text.lower()

    def first(group: str) -> tuple[int | None, list[str]]:
        terms = _DIRECTION_TERMS[group]
        return _earliest_position(lowered, terms), _find_terms(lowered, terms)

    if event_type == EventType.MONETARY_POLICY:
        tighten_pos, tighten_hits = first("tighten")
        ease_pos, ease_hits = first("ease")
        hold_pos, hold_hits = first("hold")
        candidates = [(tighten_pos, Direction.TIGHTENING), (ease_pos, Direction.EASING), (hold_pos, None)]
        candidates = [(pos, direction) for pos, direction in candidates if pos is not None]
        if candidates:
            pos, direction = min(candidates, key=lambda item: item[0])
            if direction is not None:
                return direction, (tighten_hits if direction == Direction.TIGHTENING else ease_hits)
            hawkish = _find_terms(
                lowered, ["hawkish", "higher for longer", "elevated inflation", "restrictive", "鹰派"]
            )
            dovish = _find_terms(lowered, ["dovish", "slowdown", "weakening", "cool", "cools", "cooling", "cuts", "鸽派", "衰退"])
            if hawkish and not dovish:
                return Direction.HAWKISH_HOLD, hold_hits + hawkish
            if dovish and not hawkish:
                return Direction.DOVISH_HOLD, hold_hits + dovish
            return Direction.NEUTRAL, hold_hits
        return Direction.NEUTRAL, []

    if event_type in {EventType.INFLATION, EventType.LABOR_MARKET}:
        # Surprise language dominates the raw verb: "payrolls rose but missed
        # expectations" is a downside surprise, not an upside one.
        explicit_down = _find_terms(
            lowered,
            [
                "below expectations", "below consensus", "lower than expected",
                "weaker than expected", "misses expectations", "missed expectations",
                "miss", "misses", "cooler than expected", "低于预期", "不及预期",
            ],
        )
        explicit_up = _find_terms(
            lowered,
            [
                "above expectations", "above consensus", "higher than expected",
                "hotter than expected", "stronger than expected", "beats expectations",
                "beat expectations", "beating expectations", "超预期", "高于预期",
            ],
        )
        if explicit_down and not explicit_up:
            return Direction.DOWNSIDE, explicit_down
        if explicit_up and not explicit_down:
            return Direction.UPSIDE, explicit_up
        up_pos, up_hits = first("upside")
        down_pos, down_hits = first("downside")
        candidates = [(up_pos, Direction.UPSIDE, up_hits), (down_pos, Direction.DOWNSIDE, down_hits)]
        candidates = [item for item in candidates if item[0] is not None]
        if candidates:
            _, direction, hits = min(candidates, key=lambda item: item[0])
            return direction, hits
        return Direction.NEUTRAL, []

    mapping = {
        EventType.TRADE_POLICY: [("escalation", Direction.ESCALATION), ("deescalation", Direction.DEESCALATION)],
        EventType.ENERGY_SUPPLY: [("supply_cut", Direction.SUPPLY_CUT), ("supply_increase", Direction.SUPPLY_INCREASE)],
        EventType.GEOPOLITICS: [("risk_off", Direction.RISK_OFF), ("risk_on", Direction.RISK_ON)],
        EventType.FINANCIAL_STABILITY: [("stress", Direction.STRESS)],
        EventType.FISCAL_POLICY: [("stimulus", Direction.STIMULUS), ("tighten", Direction.TIGHTENING)],
        EventType.CHINA_POLICY: [("stimulus", Direction.STIMULUS), ("tighten", Direction.TIGHTENING)],
        EventType.LABOR_MARKET: [("upside", Direction.UPSIDE), ("downside", Direction.DOWNSIDE)],
    }.get(event_type, [])
    candidates = []
    for group, direction in mapping:
        pos, hits = first(group)
        if pos is not None:
            candidates.append((pos, direction, hits))
    if candidates:
        _, direction, hits = min(candidates, key=lambda item: item[0])
        return direction, hits
    if event_type == EventType.TRADE_POLICY and "tariff" in lowered:
        return Direction.ESCALATION, ["tariff"]
    if event_type == EventType.ENERGY_SUPPLY:
        if "cut" in lowered or "减产" in lowered:
            return Direction.SUPPLY_CUT, ["cut"]
        if "increase" in lowered or "raise" in lowered or "增产" in lowered:
            return Direction.SUPPLY_INCREASE, ["increase"]
    return Direction.NEUTRAL, []


def _surprise_for(text: str, event_type: EventType) -> Surprise:
    surprise = detect_surprise(text)
    lowered = text.lower()
    if surprise.sign == "neutral" and event_type == EventType.MONETARY_POLICY:
        if "surprise" in lowered or "emergency" in lowered or "unscheduled" in lowered:
            surprise = Surprise(
                value=surprise.value,
                unit=surprise.unit,
                sign="positive",
                raw="surprise / emergency",
            )
    return surprise


class EventExtractor:
    def __init__(self, sentiment: FinancialSentiment | None = None):
        self.sentiment = sentiment or FinancialSentiment()

    def extract(self, news: NewsItem) -> MacroEvent:
        event, _debug = self.extract_with_debug(news)
        return event

    def extract_with_debug(self, news: NewsItem) -> tuple[MacroEvent, dict]:
        text = news.text
        event_type, scores, type_hits = classify_event_type(text)
        direction, direction_hits = classify_direction(text, event_type)
        magnitude = best_magnitude(text, event_type.value)
        surprise = _surprise_for(text, event_type)
        actor = entities.actor(text)
        entity_names = entities.entity_names(text)
        sentiment = self.sentiment.score(text)

        if event_type == EventType.OTHER:
            type_confidence = 0.2
        else:
            ordered = sorted(scores.values(), reverse=True)
            margin = ordered[0] - (ordered[1] if len(ordered) > 1 else 0.0)
            type_confidence = min(0.92, 0.45 + 0.08 * min(ordered[0], 4.0) + 0.04 * min(margin, 2.0))
        if direction == Direction.NEUTRAL:
            direction_confidence = 0.4
        elif direction in {Direction.HAWKISH_HOLD, Direction.DOVISH_HOLD}:
            direction_confidence = 0.62
        else:
            direction_confidence = 0.82
        confidence = round(max(0.15, min(0.94, 0.65 * type_confidence + 0.35 * direction_confidence)), 4)

        keywords: list[str] = []
        for token in type_hits + direction_hits + sentiment.hits + entity_names:
            if token and token not in keywords:
                keywords.append(token)

        event_id = hashlib.sha1(
            f"{news.title}|{news.published_at.isoformat()}".encode("utf-8")
        ).hexdigest()[:16]

        published_at = news.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        event = MacroEvent(
            id=f"evt-{event_id}",
            headline=news.title,
            summary=news.summary,
            published_at=published_at,
            source=SourceRef(
                name=news.source_name,
                url=news.url,
                tier=news.source_tier if isinstance(news.source_tier, SourceTier) else SourceTier.MEDIA,
                published_at=published_at,
            ),
            event_type=event_type,
            direction=direction,
            actor=actor,
            magnitude=magnitude,
            surprise=surprise,
            keywords=keywords[:24],
            entities=entity_names,
            confidence=confidence,
            extraction_method="rules-v1",
            text_sentiment=sentiment.to_dict(),
        )
        debug = {
            "type_scores": {key.value: value for key, value in scores.items()},
            "type_hits": type_hits,
            "direction_hits": direction_hits,
            "sentiment": sentiment.to_dict(),
            "matched_entities": entity_names,
            "surprise_raw": surprise.raw,
        }
        return event, debug
