"""Financial text processing."""

from .dedupe import NewsCluster, cluster_news, jaccard, shingles, title_similarity
from .entities import actor, assets_for_text, entity_names, normalize_entities
from .extractor import EventExtractor
from .numbers import ParsedNumber, best_magnitude, detect_surprise, parse_numbers, surprise_scale
from .sentiment import FinancialSentiment, SentimentResult

__all__ = [
    "EventExtractor",
    "FinancialSentiment",
    "NewsCluster",
    "ParsedNumber",
    "SentimentResult",
    "actor",
    "assets_for_text",
    "best_magnitude",
    "cluster_news",
    "detect_surprise",
    "entity_names",
    "jaccard",
    "normalize_entities",
    "parse_numbers",
    "shingles",
    "surprise_scale",
    "title_similarity",
]
