"""Market-data access with an offline snapshot as the default source."""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from ..config import Settings
from .base import BaseConnector, DataSourceError

DEFAULT_ASSETS = ["SPY", "QQQ", "TLT", "IEF", "UUP", "GLD", "XLE", "XLU", "EEM", "HYG", "^VIX", "FXI"]

ASSET_LABELS = {
    "SPY": "US large-cap equities",
    "QQQ": "US growth / tech equities",
    "TLT": "20y+ US Treasuries",
    "IEF": "7-10y US Treasuries",
    "UUP": "US dollar index",
    "GLD": "Gold",
    "XLE": "US energy equities",
    "XLU": "US utilities",
    "EEM": "EM equities",
    "HYG": "US high-yield credit",
    "^VIX": "VIX implied volatility",
    "FXI": "China large-cap equities",
}


class MarketData(BaseConnector):
    name = "yahoo"
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.snapshot_path = settings.prices_path
        self._snapshot: pd.DataFrame | None = None

    # ------------------------------------------------------------- snapshot
    def load_snapshot(self) -> pd.DataFrame:
        if self._snapshot is None:
            if not self.snapshot_path.exists():
                raise DataSourceError(
                    f"missing market snapshot at {self.snapshot_path}; "
                    "run scripts/fetch_market_snapshot.py"
                )
            frame = pd.read_csv(self.snapshot_path, parse_dates=["date"])
            frame["ticker"] = frame["ticker"].astype(str)
            self._snapshot = frame.sort_values(["date", "ticker"]).reset_index(drop=True)
        return self._snapshot.copy()

    def prices_wide(self, field: str = "adj_close", tickers: list[str] | None = None) -> pd.DataFrame:
        frame = self.load_snapshot()
        if tickers:
            frame = frame[frame["ticker"].isin(tickers)]
        wide = (
            frame.pivot(index="date", columns="ticker", values=field)
            .sort_index()
            .dropna(how="all")
        )
        return wide

    def returns(self, tickers: list[str] | None = None) -> pd.DataFrame:
        prices = self.prices_wide("adj_close", tickers)
        return prices.pct_change().dropna(how="all")

    def provenance(self) -> dict:
        path = self.snapshot_path.parent / "provenance.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"source": "local snapshot", "path": str(self.snapshot_path)}

    # ----------------------------------------------------------------- live
    def fetch_daily(
        self,
        symbol: str,
        start: dt.date,
        end: dt.date | None = None,
    ) -> pd.DataFrame:
        end = end or dt.date.today()
        params = {
            "period1": int(dt.datetime.combine(start, dt.time.min).timestamp()),
            "period2": int(dt.datetime.combine(end, dt.time.min).timestamp()),
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
        response = self.get_json(
            self.base_url.format(symbol=symbol),
            params=params,
            cache_key=f"chart:{symbol}:{start}:{end}",
            ttl_seconds=6 * 3600,
            headers={"Accept": "application/json"},
        )
        payload = response.payload
        try:
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            adj = result["indicators"]["adjclose"][0]["adjclose"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSourceError(f"unexpected Yahoo payload for {symbol}") from exc

        rows = []
        for ts, close, adj_close, volume in zip(
            timestamps, quote["close"], adj, quote["volume"], strict=False
        ):
            if close is None or adj_close is None:
                continue
            rows.append(
                {
                    "date": dt.datetime.fromtimestamp(ts, dt.timezone.utc).date(),
                    "ticker": symbol,
                    "close": close,
                    "adj_close": adj_close,
                    "volume": volume or 0,
                }
            )
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise DataSourceError(f"no observations returned for {symbol}")
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.sort_values("date").reset_index(drop=True)

    def latest_close(self, symbol: str) -> dict:
        end = dt.date.today()
        start = end - dt.timedelta(days=10)
        frame = self.fetch_daily(symbol, start, end)
        last = frame.iloc[-1]
        return {
            "symbol": symbol,
            "date": last["date"].date().isoformat(),
            "close": float(last["close"]),
            "source": "Yahoo Finance chart API",
        }
