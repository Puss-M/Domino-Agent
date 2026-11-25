"""HTTP plumbing shared by the data connectors.

Design rules:
- Every request is cached with its URL and retrieval timestamp.
- Retries are explicit and bounded; a failed source raises instead of silently
  returning an empty frame.
- Request pacing is per-connector so a batch job cannot trip a public API's
  rate limit.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from ..config import Settings, ensure_cache_dir


class DataSourceError(RuntimeError):
    pass


@dataclass
class CachedResponse:
    payload: Any
    url: str
    retrieved_at: datetime
    from_cache: bool


class BaseConnector:
    name = "base"
    base_url = ""
    min_interval = 0.15

    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.cache_dir = ensure_cache_dir(settings) / self.name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})
        self._last_request_at = 0.0

    # ------------------------------------------------------------------ cache
    def _cache_file(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_file(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, key: str, url: str, payload: Any) -> datetime:
        retrieved_at = datetime.now(timezone.utc)
        record = {
            "url": url,
            "retrieved_at": retrieved_at.isoformat(),
            "payload": payload,
        }
        self._cache_file(key).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
        return retrieved_at

    # ------------------------------------------------------------------ http
    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        cache_key: str | None = None,
        ttl_seconds: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> CachedResponse:
        key = cache_key or f"{url}?{json.dumps(params or {}, sort_keys=True)}"
        cached = self._read_cache(key)
        if cached:
            retrieved_at = datetime.fromisoformat(cached["retrieved_at"])
            age = (datetime.now(timezone.utc) - retrieved_at).total_seconds()
            if ttl_seconds is None or age <= ttl_seconds:
                return CachedResponse(
                    payload=cached["payload"],
                    url=cached["url"],
                    retrieved_at=retrieved_at,
                    from_cache=True,
                )

        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            self._pace()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.settings.request_timeout,
                )
                self._last_request_at = time.monotonic()
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise DataSourceError(
                        f"{self.name}: HTTP {response.status_code} for {response.url}"
                    )
                response.raise_for_status()
                payload = response.json()
                retrieved_at = self._write_cache(key, response.url, payload)
                return CachedResponse(
                    payload=payload,
                    url=response.url,
                    retrieved_at=retrieved_at,
                    from_cache=False,
                )
            except (requests.RequestException, ValueError, DataSourceError) as exc:
                last_error = exc
                if attempt + 1 < self.settings.max_retries:
                    time.sleep(1.5 * (attempt + 1))
        raise DataSourceError(f"{self.name}: request failed ({last_error})") from last_error

    def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        cache_key: str | None = None,
        ttl_seconds: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> CachedResponse:
        key = cache_key or f"text:{url}?{json.dumps(params or {}, sort_keys=True)}"
        cached = self._read_cache(key)
        if cached:
            retrieved_at = datetime.fromisoformat(cached["retrieved_at"])
            age = (datetime.now(timezone.utc) - retrieved_at).total_seconds()
            if ttl_seconds is None or age <= ttl_seconds:
                return CachedResponse(
                    payload=cached["payload"],
                    url=cached["url"],
                    retrieved_at=retrieved_at,
                    from_cache=True,
                )

        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            self._pace()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.settings.request_timeout,
                )
                self._last_request_at = time.monotonic()
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise DataSourceError(
                        f"{self.name}: HTTP {response.status_code} for {response.url}"
                    )
                response.raise_for_status()
                retrieved_at = self._write_cache(key, response.url, response.text)
                return CachedResponse(
                    payload=response.text,
                    url=response.url,
                    retrieved_at=retrieved_at,
                    from_cache=False,
                )
            except (requests.RequestException, DataSourceError) as exc:
                last_error = exc
                if attempt + 1 < self.settings.max_retries:
                    time.sleep(1.5 * (attempt + 1))
        raise DataSourceError(f"{self.name}: request failed ({last_error})") from last_error
