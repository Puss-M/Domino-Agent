"""World Bank indicator API: annual macro context, no key required.

Annual data is not suitable for event studies; it is used for regime context
(e.g., inflation level, GDP growth) and for a cheap, reproducible data-source
smoke test.
"""

from __future__ import annotations

import pandas as pd

from .base import BaseConnector, DataSourceError

INDICATORS = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "gdp_current_usd": "NY.GDP.MKTP.CD",
    "inflation_cpi": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "govt_debt_gdp": "GC.DOD.TOTL.GD.ZS",
}


class WorldBank(BaseConnector):
    name = "worldbank"
    base_url = "https://api.worldbank.org/v2"

    def indicator(
        self,
        country: str,
        indicator: str,
        start_year: int = 2000,
        end_year: int = 2025,
    ) -> pd.DataFrame:
        code = INDICATORS.get(indicator, indicator)
        url = f"{self.base_url}/country/{country}/indicator/{code}"
        params = {
            "format": "json",
            "per_page": 1000,
            "date": f"{start_year}:{end_year}",
        }
        payload = self.get_json(url, params=params, ttl_seconds=7 * 86400).payload
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            raise DataSourceError(f"World Bank returned no observations for {country}/{code}")
        rows = [
            {
                "country": row.get("country", {}).get("value"),
                "indicator": row.get("indicator", {}).get("value"),
                "year": int(row["date"]),
                "value": row["value"],
            }
            for row in payload[1]
        ]
        frame = pd.DataFrame(rows).sort_values("year")
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        return frame.dropna(subset=["value"]).reset_index(drop=True)

    def latest(self, country: str, indicator: str) -> dict:
        frame = self.indicator(country, indicator)
        if frame.empty:
            raise DataSourceError(f"no {indicator} for {country}")
        last = frame.iloc[-1]
        return {
            "country": country,
            "indicator": indicator,
            "year": int(last["year"]),
            "value": float(last["value"]),
        }
