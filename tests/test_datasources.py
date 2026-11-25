from __future__ import annotations

from backend.app.config import get_settings
from backend.app.datasources.market import MarketData
from backend.app.datasources.sec import html_to_text


def test_market_snapshot_has_all_assets():
    market = MarketData(get_settings())
    prices = market.prices_wide("adj_close")
    assert "SPY" in prices.columns
    assert "QQQ" in prices.columns
    assert "^VIX" in prices.columns
    assert len(prices) > 2000
    assert prices["SPY"].dropna().iloc[-1] > 0


def test_sec_html_strips_scripts_and_entities():
    raw = "<html><script>bad()</script><p>Net sales&nbsp;rose 5%.</p><p>EPS was $1.64.</p></html>"
    text = html_to_text(raw)
    assert "Net sales rose 5%." in text
    assert "EPS was $1.64." in text
    assert "bad()" not in text
