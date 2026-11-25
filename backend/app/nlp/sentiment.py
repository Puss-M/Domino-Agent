"""Finance-aware lexical sentiment.

Two deliberate choices separate this from a generic sentiment demo:

1. The categories are the ones used in financial text research: polarity,
   uncertainty, hawkish/dovish tone, and risk-on/risk-off. "Liability" is not
   automatically negative and "higher" is not automatically positive.
2. The shipped lexicon is a small, auditable seed. The official
   Loughran-McDonald master dictionary is *not* redistributed here; if you have
   a licensed copy, point DOMINO_LM_DICTIONARY at the CSV and it will be merged.

The output is a feature, not a verdict. The event extractor and the mechanism
retriever decide what the tone means for a specific transmission channel.
"""

from __future__ import annotations

import csv
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*|[\u4e00-\u9fff]+")

_NEGATORS = {"not", "no", "never", "without", "n't", "cannot", "can't", "fails", "failed", "unlikely"}
_INTENSIFIERS = {
    "sharply": 1.6,
    "significantly": 1.5,
    "substantially": 1.5,
    "much": 1.3,
    "very": 1.3,
    "extremely": 1.7,
    "slightly": 0.6,
    "modestly": 0.7,
    "marginally": 0.6,
}

LEXICON: dict[str, dict[str, float]] = {
    "positive": {
        "beat": 1.0, "beats": 1.0, "exceed": 1.0, "exceeds": 1.0, "upgrade": 1.0,
        "profit": 0.8, "profits": 0.8, "growth": 0.8, "strong": 1.0, "resilient": 0.8,
        "recovery": 0.9, "rebound": 1.0, "rally": 1.0, "surge": 0.8, "gain": 0.7,
        "gains": 0.7, "improve": 0.7, "improves": 0.7, "expansion": 0.8, "deal": 0.8,
        "truce": 1.0, "ceasefire": 1.2, "exemption": 0.8, "pause": 0.6, "stimulus": 1.0,
        "support": 0.5, "easing": 0.8, "dovish": 1.0, "soft landing": 1.2,
        "上涨": 0.8, "增长": 0.8, "强劲": 1.0, "反弹": 1.0, "刺激": 1.0, "停火": 1.2,
    },
    "negative": {
        "miss": 1.0, "misses": 1.0, "missed": 1.0, "downgrade": 1.0, "loss": 0.9, "losses": 0.9,
        "layoff": 1.0, "layoffs": 1.0, "bankruptcy": 1.3, "default": 1.3, "recession": 1.3,
        "crisis": 1.3, "collapse": 1.4, "contagion": 1.4, "war": 1.3, "invasion": 1.4,
        "attack": 1.1, "sanction": 1.0, "sanctions": 1.0, "tariff": 1.0, "tariffs": 1.0,
        "strike": 0.8, "shutdown": 1.0, "hawkish": 0.9, "tightening": 0.8, "slowdown": 1.0,
        "selloff": 1.2, "volatility": 0.8, "uncertainty": 0.9, "downturn": 1.1, "crunch": 1.2,
        "下跌": 0.9, "衰退": 1.3, "危机": 1.3, "暴跌": 1.4, "关税": 1.0, "战争": 1.3,
    },
    "uncertainty": {
        "may": 0.5, "might": 0.5, "could": 0.5, "uncertain": 1.0, "uncertainty": 1.0,
        "unclear": 1.0, "risk": 0.7, "risks": 0.7, "potential": 0.6, "if": 0.3,
        "whether": 0.4, "estimate": 0.5, "preliminary": 0.7, "expected": 0.4, "outlook": 0.5,
        "可能": 0.5, "不确定": 1.0, "风险": 0.7, "预计": 0.5,
    },
    "hawkish": {
        "hike": 1.0, "hikes": 1.0, "raise": 0.8, "raises": 0.8, "tighten": 1.0,
        "tightening": 1.0, "hawkish": 1.2, "higher for longer": 1.4, "elevated inflation": 1.1,
        "strong jobs": 0.9, "upside surprise": 1.0, "restrictive": 0.8, "加息": 1.0,
        "收紧": 1.0, "鹰派": 1.2, "通胀高企": 1.1,
    },
    "dovish": {
        "cut": 0.8, "cuts": 0.8, "lower": 0.7, "ease": 1.0, "easing": 1.0, "dovish": 1.2,
        "pause": 0.7, "disinflation": 1.0, "weakening": 0.8, "slowdown": 0.9, "降息": 1.0,
        "宽松": 1.0, "鸽派": 1.2, "通胀回落": 1.0,
    },
    "risk_off": {
        "war": 1.2, "invasion": 1.4, "attack": 1.1, "crisis": 1.2, "collapse": 1.4,
        "default": 1.3, "contagion": 1.4, "selloff": 1.2, "flight to safety": 1.3,
        "bank failure": 1.4, "bank run": 1.4, "credit crunch": 1.3, "escalation": 1.1,
        "战争": 1.2, "入侵": 1.4, "危机": 1.2, "抛售": 1.2, "升级": 1.1,
    },
    "risk_on": {
        "ceasefire": 1.3, "truce": 1.2, "deal": 0.8, "stimulus": 1.0, "rebound": 1.0,
        "rally": 1.0, "soft landing": 1.2, "de-escalation": 1.2, "exemption": 0.8,
        "停火": 1.3, "协议": 0.8, "刺激": 1.0, "反弹": 1.0,
    },
}

_PHRASES = {
    "higher for longer": ("hawkish", 1.4),
    "soft landing": ("risk_on", 1.2),
    "flight to safety": ("risk_off", 1.3),
    "credit crunch": ("risk_off", 1.3),
    "bank run": ("risk_off", 1.4),
    "bank failure": ("risk_off", 1.4),
    "cut guidance": ("negative", 1.0),
    "lowered guidance": ("negative", 1.0),
    "basis points": ("neutral", 0.0),
}


@dataclass
class SentimentResult:
    polarity: float
    uncertainty: float
    hawkish: float
    dovish: float
    risk_off: float
    risk_on: float
    hits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, float]:
        return {
            "polarity": round(self.polarity, 4),
            "uncertainty": round(self.uncertainty, 4),
            "hawkish": round(self.hawkish, 4),
            "dovish": round(self.dovish, 4),
            "risk_off": round(self.risk_off, 4),
            "risk_on": round(self.risk_on, 4),
        }


def _load_lm_dictionary(path: str) -> dict[str, dict[str, float]]:
    """Merge a user-supplied Loughran-McDonald CSV (not redistributed)."""
    merged: dict[str, dict[str, float]] = {category: {} for category in LEXICON}
    with Path(path).open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            word = (row.get("Word") or "").strip().lower()
            if not word:
                continue
            if row.get("Positive") == "1":
                merged["positive"][word] = 1.0
            if row.get("Negative") == "1":
                merged["negative"][word] = 1.0
            if row.get("Uncertainty") == "1":
                merged["uncertainty"][word] = 1.0
            if row.get("StrongModal") == "1" or row.get("WeakModal") == "1":
                merged["uncertainty"][word] = max(merged["uncertainty"].get(word, 0.0), 0.6)
    return merged


class FinancialSentiment:
    def __init__(self, lm_dictionary_path: str | None = None):
        self.lexicon = {category: dict(words) for category, words in LEXICON.items()}
        path = lm_dictionary_path or os.getenv("DOMINO_LM_DICTIONARY")
        if path and Path(path).exists():
            extra = _load_lm_dictionary(path)
            for category, words in extra.items():
                self.lexicon[category].update(words)

    def score(self, text: str) -> SentimentResult:
        lowered = text.lower()
        hits: list[str] = []
        counts = {category: 0.0 for category in ("positive", "negative", "uncertainty", "hawkish", "dovish", "risk_off", "risk_on")}

        # Multi-word phrases first, then token-level entries.
        for phrase, (category, weight) in _PHRASES.items():
            occurrences = lowered.count(phrase)
            if occurrences and category in counts:
                counts[category] += weight * occurrences
                hits.append(phrase)

        tokens = [(m.group(0).lower(), m.start(), m.end()) for m in _TOKEN_RE.finditer(lowered)]
        for index, (token, start, _end) in enumerate(tokens):
            negated = any(tokens[j][0] in _NEGATORS for j in range(max(0, index - 3), index))
            multiplier = 1.0
            if index > 0 and tokens[index - 1][0] in _INTENSIFIERS:
                multiplier = _INTENSIFIERS[tokens[index - 1][0]]
            for category in counts:
                weight = self.lexicon[category].get(token)
                if weight is None:
                    continue
                signed = weight * multiplier
                if negated and category in {"positive", "negative", "hawkish", "dovish", "risk_off", "risk_on"}:
                    # Move the weight to the opposite side of the same axis.
                    opposite = {
                        "positive": "negative",
                        "negative": "positive",
                        "hawkish": "dovish",
                        "dovish": "hawkish",
                        "risk_off": "risk_on",
                        "risk_on": "risk_off",
                    }[category]
                    counts[opposite] += signed
                else:
                    counts[category] += signed
                hits.append(token)

        # Chinese terms are scanned as substrings; a preceding 不/未/无 flips them.
        for category, words in self.lexicon.items():
            for word, weight in words.items():
                if not re.search(r"[\u4e00-\u9fff]", word):
                    continue
                for match in re.finditer(re.escape(word), lowered):
                    negated = match.start() > 0 and lowered[match.start() - 1] in "不未无"
                    target = category
                    if negated and category in {"positive", "negative", "hawkish", "dovish", "risk_off", "risk_on"}:
                        target = {
                            "positive": "negative",
                            "negative": "positive",
                            "hawkish": "dovish",
                            "dovish": "hawkish",
                            "risk_off": "risk_on",
                            "risk_on": "risk_off",
                        }[category]
                    counts[target] += weight
                    hits.append(word)

        return SentimentResult(
            polarity=math.tanh(0.55 * (counts["positive"] - counts["negative"])),
            uncertainty=math.tanh(0.45 * counts["uncertainty"]),
            hawkish=math.tanh(0.5 * counts["hawkish"]),
            dovish=math.tanh(0.5 * counts["dovish"]),
            risk_off=math.tanh(0.55 * counts["risk_off"]),
            risk_on=math.tanh(0.55 * counts["risk_on"]),
            hits=sorted(set(hits)),
        )
