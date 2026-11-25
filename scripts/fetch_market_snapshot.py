"""Download a reproducible daily price snapshot from Yahoo Finance's chart API.

The output is intentionally a flat CSV plus a provenance file so the repository
can be cloned and evaluated without network access or an API key.

Usage:
    python scripts/fetch_market_snapshot.py --start 2015-01-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import requests

TICKERS = ["SPY", "QQQ", "TLT", "IEF", "UUP", "GLD", "XLE", "XLU", "EEM", "HYG", "^VIX", "FXI"]
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def fetch(symbol: str, start: dt.date, end: dt.date) -> dict:
    params = {
        "period1": int(dt.datetime.combine(start, dt.time.min).timestamp()),
        "period2": int(dt.datetime.combine(end, dt.time.min).timestamp()),
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = requests.get(
                BASE.format(symbol=symbol), params=params, headers=HEADERS, timeout=40
            )
            if response.status_code == 429:
                raise RuntimeError("rate limited (HTTP 429)")
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - retry boundary
            last_error = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {symbol}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument(
        "--out", default=str(Path(__file__).resolve().parents[1] / "backend" / "data" / "market")
    )
    args = parser.parse_args()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = ["date,ticker,close,adj_close,volume"]
    provenance = {
        "source": "Yahoo Finance chart API",
        "endpoint": BASE,
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "requested_window": {"start": start.isoformat(), "end": end.isoformat()},
        "price_field": "adjusted close (dividends and splits reinvested)",
        "tickers": {},
        "caveats": [
            "Yahoo Finance is a convenience endpoint, not an exchange feed.",
            "Adjusted close can be revised after corporate actions; do not treat as point-in-time.",
            "Survivorship and listing changes are not modelled.",
        ],
    }

    for symbol in TICKERS:
        payload = fetch(symbol, start, end)
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        adj = result["indicators"]["adjclose"][0]["adjclose"]
        count = 0
        for ts, close, adj_close, volume in zip(
            timestamps, quote["close"], adj, quote["volume"], strict=False
        ):
            if close is None or adj_close is None:
                continue
            date = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
            rows.append(f"{date},{symbol},{close:.6f},{adj_close:.6f},{volume or 0}")
            count += 1
        provenance["tickers"][symbol] = {
            "rows": count,
            "first_date": dt.datetime.fromtimestamp(timestamps[0], dt.timezone.utc).date().isoformat(),
            "last_date": dt.datetime.fromtimestamp(timestamps[-1], dt.timezone.utc).date().isoformat(),
            "currency": result["meta"].get("currency"),
        }
        print(f"{symbol}: {count} rows")
        time.sleep(1.5)

    (out / "prices.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (out / "provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(rows) - 1} rows to {out}")


if __name__ == "__main__":
    main()
