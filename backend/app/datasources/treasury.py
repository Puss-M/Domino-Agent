"""US Treasury daily yield-curve CSV (no key required)."""

from __future__ import annotations

import io

import pandas as pd

from .base import BaseConnector, DataSourceError


class TreasuryYields(BaseConnector):
    name = "treasury"
    base_url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        "daily-treasury-rates.csv/{year}/all"
    )

    def year(self, year: int) -> pd.DataFrame:
        url = self.base_url.format(year=year)
        params = {
            "type": "daily_treasury_yield_curve",
            "field_tdr_date_value": str(year),
            "page": "",
            "_format": "csv",
        }
        text = self.get_text(url, params=params, ttl_seconds=7 * 86400).payload
        try:
            frame = pd.read_csv(io.StringIO(text))
        except Exception as exc:  # noqa: BLE001 - parser boundary
            raise DataSourceError(f"could not parse Treasury CSV for {year}") from exc
        if "Date" not in frame.columns:
            raise DataSourceError(f"unexpected Treasury CSV columns: {frame.columns.tolist()}")
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.rename(columns={"Date": "date"}).sort_values("date").reset_index(drop=True)
        return frame

    def latest_curve(self, year: int | None = None) -> dict:
        year = year or pd.Timestamp.today().year
        frame = self.year(year)
        last = frame.iloc[-1]
        return {
            "date": last["date"].date().isoformat(),
            "2y": float(last["2 Yr"]),
            "10y": float(last["10 Yr"]),
            "30y": float(last["30 Yr"]),
            "source": "US Treasury daily yield curve",
        }
