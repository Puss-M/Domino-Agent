"""Refresh the small, redistributable public-data snapshots used for demos.

These are not required for the core analysis, which runs from the bundled
market/event/knowledge files. They demonstrate the live connectors and give
reviewers a real filing/news example without an API key.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings
from backend.app.datasources import GdeltNews, SecEdgar, TreasuryYields
from backend.app.nlp.dedupe import cluster_news

DATA = ROOT / "backend" / "data"


def main() -> None:
    settings = get_settings()
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")

    macro_dir = DATA / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    treasury = TreasuryYields(settings)
    curve = treasury.year(2024)
    curve.to_csv(macro_dir / "treasury_yields_2024.csv", index=False)
    print(f"treasury: {len(curve)} rows")

    sec_dir = DATA / "sec"
    sec_dir.mkdir(parents=True, exist_ok=True)
    sec = SecEdgar(settings)
    releases = sec.press_release("AAPL", limit=1)
    revenue = sec.metric_history(
        "AAPL", "RevenueFromContractWithCustomerExcludingAssessedTax", "USD", limit=12
    )
    if not revenue:
        revenue = sec.metric_history("AAPL", "Revenues", "USD", limit=12)
    payload = {
        "retrieved_at": retrieved,
        "source": "SEC EDGAR",
        "ticker": "AAPL",
        "press_release": releases[0] if releases else None,
        "revenue_history": revenue,
        "caveats": [
            "The 8-K exhibit is public domain but may be large; it is truncated for the demo.",
            "XBRL values can be restated in later filings; use the `filed` field for as-filed reconstruction.",
        ],
    }
    if payload["press_release"]:
        payload["press_release"]["text"] = payload["press_release"]["text"][:20000]
    (sec_dir / "aapl_sample.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"sec: 8-K={'yes' if releases else 'no'}, revenue rows={len(revenue)}")

    news_dir = DATA / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    gdelt = GdeltNews(settings)
    items = gdelt.search("federal reserve", timespan="1week", max_records=20)
    clusters = cluster_news(items, threshold=0.7)
    (news_dir / "gdelt_fed_sample.json").write_text(
        json.dumps(
            {
                "retrieved_at": retrieved,
                "source": "GDELT 2.0 DOC API",
                "query": "federal reserve",
                "n_items": len(items),
                "n_clusters": len(clusters),
                "clusters": [cluster.to_dict() for cluster in clusters],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"gdelt: {len(items)} items, {len(clusters)} clusters")


if __name__ == "__main__":
    main()
