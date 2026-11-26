"""E13: cross-sectional rank + cost-aware evaluation for every benchmark.

Output: docs/results/cross_sectional_rank.json + console table.
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
from backend.app.evaluation.cross_sectional import evaluate_cross_sectional
from backend.app.evaluation.dataset import DATASETS, load_events
from backend.app.schemas import BacktestConfig


def main() -> None:
    settings = get_settings()
    market = MarketData(settings)
    assets = [
        "SPY",
        "QQQ",
        "TLT",
        "IEF",
        "UUP",
        "GLD",
        "XLE",
        "XLU",
        "EEM",
        "HYG",
        "^VIX",
        "FXI",
    ]
    prices = market.prices_wide("adj_close", assets + ["SPY"]).dropna(how="all")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": "expanding-window by event; target = within-event CAR rank; net = gross - 2 * one-way bps",
        "datasets": {},
    }
    for dataset in DATASETS:
        events = load_events(settings=settings, dataset=dataset)
        result = evaluate_cross_sectional(
            events, prices, assets, BacktestConfig(dataset=dataset)
        )
        report["datasets"][dataset] = result
        print(f"### {dataset} events={result['n_events']} rows={result['n_rows']} folds={result['n_folds']}")
        for name in ("lightgbm", "ridge", "momentum", "random"):
            metrics = result["models"].get(name, {})
            print(
                f"  {name:9s} IC={metrics.get('mean_rank_ic')} "
                f"IR={metrics.get('rank_ic_ir')} "
                f"LS={metrics.get('gross_ls_bps')}bps "
                f"CI={metrics.get('gross_ls_ci')} "
                f"net10={metrics.get('net_ls_bps', {}).get('10')}bps"
            )

    path = ROOT / "docs" / "results" / "cross_sectional_rank.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
