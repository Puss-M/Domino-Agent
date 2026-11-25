"""FRED / ALFRED connector.

Set FRED_API_KEY to enable. The `vintage` arguments map to ALFRED's
realtime_start/realtime_end, which is the difference between a point-in-time
backtest and a look-ahead-biased one.
"""

from __future__ import annotations

import os

from .base import BaseConnector, DataSourceError


class Fred(BaseConnector):
    name = "fred"
    base_url = "https://api.stlouisfed.org/fred"

    def __init__(self, settings):
        super().__init__(settings)
        self.api_key = os.getenv("FRED_API_KEY")

    def _require_key(self) -> str:
        if not self.api_key:
            raise DataSourceError(
                "FRED_API_KEY is not set; FRED/ALFRED access is disabled. "
                "The rest of Domino Agent runs from the bundled snapshot."
            )
        return self.api_key

    def series(
        self,
        series_id: str,
        start: str = "2000-01-01",
        end: str = "2025-12-31",
        vintage: str | None = None,
    ) -> list[dict]:
        params = {
            "series_id": series_id,
            "api_key": self._require_key(),
            "file_type": "json",
            "observation_start": start,
            "observation_end": end,
        }
        if vintage:
            params["realtime_start"] = vintage
            params["realtime_end"] = vintage
        payload = self.get_json(
            f"{self.base_url}/series/observations",
            params=params,
            ttl_seconds=86400,
        ).payload
        return payload.get("observations", [])

    def metadata(self, series_id: str) -> dict:
        payload = self.get_json(
            f"{self.base_url}/series",
            params={"series_id": series_id, "api_key": self._require_key(), "file_type": "json"},
            ttl_seconds=30 * 86400,
        ).payload
        series = payload.get("seriess", [])
        if not series:
            raise DataSourceError(f"unknown FRED series {series_id}")
        return series[0]
