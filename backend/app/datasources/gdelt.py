"""GDELT 2.0 news search.

GDELT is useful for breadth (global, multilingual) but it is a *discovery*
layer: article text is not included, deduplication is essential, and tone is
not in the DOC article list. We therefore treat it as a source of headlines
and URLs, not as ground truth.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..schemas import NewsItem, SourceTier
from .base import BaseConnector, DataSourceError


class GdeltNews(BaseConnector):
    name = "gdelt"
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"

    def search(
        self,
        query: str,
        *,
        timespan: str = "1week",
        max_records: int = 25,
        language: str | None = None,
    ) -> list[NewsItem]:
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": min(max_records, 250),
            "format": "json",
            "timespan": timespan,
            "sort": "hybridrel",
        }
        if language:
            params["query"] = f"{query} sourcelang:{language}"
        response = self.get_json(
            self.base_url, params=params, ttl_seconds=15 * 60, headers={"Accept": "application/json"}
        )
        payload = response.payload
        if not payload:
            return []
        articles = payload.get("articles", [])
        items: list[NewsItem] = []
        for article in articles:
            published = self._parse_seendate(article.get("seendate", ""))
            if not published:
                continue
            items.append(
                NewsItem(
                    id=article.get("url"),
                    title=(article.get("title") or "").strip(),
                    summary="",
                    url=article.get("url"),
                    source_name=article.get("domain") or "gdelt",
                    source_tier=SourceTier.MEDIA,
                    published_at=published,
                    language=(article.get("language") or "en").lower(),
                )
            )
        return [item for item in items if item.title]

    @staticmethod
    def _parse_seendate(raw: str) -> datetime | None:
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def tone_series(self, query: str, timespan: str = "3months") -> list[dict]:
        """Article-volume series; kept separate from tone to avoid overclaiming."""
        params = {
            "query": query,
            "mode": "timelinevol",
            "format": "json",
            "timespan": timespan,
        }
        try:
            payload = self.get_json(
                self.base_url, params=params, ttl_seconds=60 * 60
            ).payload
        except DataSourceError:
            return []
        return payload.get("timeline", []) if isinstance(payload, dict) else []
