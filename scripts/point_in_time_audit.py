"""E11: point-in-time contract audit for every benchmark.

Output: docs/results/point_in_time.json + console table.
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
from backend.app.datasources import MarketData
from backend.app.evaluation.dataset import DATASETS, load_events
from backend.app.evaluation.temporal import audit_point_in_time


def main() -> None:
    settings = get_settings()
    market = MarketData(settings)
    prices = market.prices_wide("adj_close", ["SPY"]).dropna(how="all")
    price_last = prices.index[-1].date() if len(prices.index) else None

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "contract": "backend/data/point_in_time.yaml",
        "price_snapshot_last_date": price_last.isoformat() if price_last else None,
        "datasets": {},
    }
    for dataset in DATASETS:
        events = load_events(settings=settings, dataset=dataset)
        audit = audit_point_in_time(
            events,
            dataset=dataset,
            price_last_date=price_last,
            settings=settings,
        )
        report["datasets"][dataset] = audit
        print(
            f"{dataset:14s} events={audit['n_events']:3d} "
            f"verdict={audit['verdict']:18s} "
            f"revised={','.join(audit['revised_sources'])}"
        )

    path = ROOT / "docs" / "results" / "point_in_time.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
