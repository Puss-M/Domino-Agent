"""Near-duplicate news clustering.

Syndicated headlines are the main reason naive "count the articles" sentiment
signals overstate conviction. A story that appears in 30 outlets is one story,
not 30 independent observations. This module clusters near-duplicates so the
engine can down-weight repetition and report source diversity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..schemas import NewsItem

_PUNCT_RE = re.compile(r"[^\w\s\u4e00-\u9fff]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


@dataclass
class NewsCluster:
    representative: NewsItem
    members: list[NewsItem] = field(default_factory=list)
    similarity_threshold: float = 0.7

    @property
    def duplicate_count(self) -> int:
        return max(0, len(self.members) - 1)

    @property
    def source_diversity(self) -> int:
        return len({item.source_name.lower() for item in self.members})

    @property
    def novelty(self) -> float:
        diversity = min(self.source_diversity, 3) / 3
        return round((1 / (1 + self.duplicate_count)) * (0.5 + 0.5 * diversity), 4)

    def to_dict(self) -> dict:
        return {
            "representative": self.representative.model_dump(mode="json"),
            "duplicate_count": self.duplicate_count,
            "source_diversity": self.source_diversity,
            "novelty": self.novelty,
            "members": [item.model_dump(mode="json") for item in self.members],
        }


def normalize_text(text: str) -> str:
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def shingles(text: str, size: int = 3) -> set[tuple[str, ...]]:
    tokens = normalize_text(text).split()
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(left: set, right: set) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def title_similarity(left: str, right: str) -> float:
    """Shingle Jaccard plus a character-level ratio.

    Syndicated rewrites often swap one verb ("raises" -> "lifts"), which
    destroys two or three 3-gram shingles. The character ratio keeps those
    pairs together without merging genuinely different stories.
    """
    shingle_score = jaccard(shingles(left), shingles(right))
    left_tokens = set(normalize_text(left).split())
    right_tokens = set(normalize_text(right).split())
    token_overlap = jaccard(left_tokens, right_tokens)
    if token_overlap < 0.2:
        return shingle_score
    ratio = SequenceMatcher(
        None, normalize_text(left), normalize_text(right), autojunk=False
    ).ratio()
    return max(shingle_score, 0.9 * ratio)


def cluster_news(items: list[NewsItem], threshold: float = 0.7) -> list[NewsCluster]:
    """Greedy chronological clustering; deterministic for a given input order."""
    clusters: list[NewsCluster] = []
    for item in sorted(items, key=lambda news: news.published_at):
        best: NewsCluster | None = None
        best_score = 0.0
        for cluster in clusters:
            score = title_similarity(item.title, cluster.representative.title)
            if score > best_score:
                best, best_score = cluster, score
        if best is not None and best_score >= threshold:
            best.members.append(item)
        else:
            clusters.append(
                NewsCluster(
                    representative=item,
                    members=[item],
                    similarity_threshold=threshold,
                )
            )
    return clusters
