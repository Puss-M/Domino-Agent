from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.nlp.dedupe import cluster_news, jaccard, shingles, title_similarity
from backend.app.schemas import NewsItem


def _item(title: str, source: str, minutes: int) -> NewsItem:
    return NewsItem(
        title=title,
        source_name=source,
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
    )


def test_near_duplicates_cluster():
    items = [
        _item("Fed raises rates by 50 basis points", "wire-a", 0),
        _item("Fed raises rates by 50 basis points", "wire-b", 5),
        _item("Fed lifts rates by 50 basis points", "wire-c", 10),
        _item("Oil prices fall as demand worries mount", "wire-d", 15),
    ]
    clusters = cluster_news(items, threshold=0.6)
    assert len(clusters) == 2
    biggest = max(clusters, key=lambda cluster: len(cluster.members))
    assert biggest.duplicate_count == 2
    assert biggest.source_diversity == 3
    assert 0 < biggest.novelty < 1


def test_identical_titles_have_similarity_one():
    assert title_similarity("Fed raises rates", "Fed raises rates") == 1.0


def test_unrelated_titles_have_low_similarity():
    assert title_similarity("Fed raises rates", "Oil prices fall") < 0.2


def test_shingles_and_jaccard():
    left = shingles("the fed raised rates by fifty basis points")
    right = shingles("the fed raised rates by fifty basis points")
    assert jaccard(left, right) == 1.0
