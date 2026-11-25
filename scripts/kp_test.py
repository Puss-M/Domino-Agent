"""E7: Kolari-Pynnonen cross-correlation-adjusted CAR test.

The event-study cross-section is the set of assets that price the same macro
event. Their abnormal returns are correlated, so the naive BMP t-statistic
overstates significance. This script reports both statistics per event and
aggregates them by benchmark.

Output: docs/results/kp_test.json
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
from backend.app.evaluation.event_study import (
    compute_outcomes,
    cross_sectional_test,
    event_study_summary,
)
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
        "method": "Kolari-Pynnonen (2010) adjustment of the BMP standardized CAR test",
        "window": "[0,+1] trading days; market model estimated on [-120,-21]",
        "assets": assets,
        "datasets": {},
    }
    for dataset in DATASETS:
        events = load_events(settings=settings, dataset=dataset)
        config = BacktestConfig(dataset=dataset, window_end=1)
        outcomes, skipped = compute_outcomes(events, prices, assets, config)
        result = cross_sectional_test(outcomes, events, prices, assets, config)
        report["datasets"][dataset] = {
            "n_events_loaded": len(events),
            "n_events_priced": len(outcomes),
            "n_skipped": len(skipped),
            "summary": {key: value for key, value in result.items() if key != "by_event"},
            "per_asset": [event_study_summary(outcomes, asset) for asset in assets],
            "by_event": result.get("by_event", []),
        }
        if result["n_events"]:
            pooled = result["pooled"]
            print(
                f"{dataset:14s} events={result['n_events']:3d} "
                f"rho={result['mean_rho_bar']:.3f} "
                f"|BMP|={result['mean_abs_bmp_t']:.2f} "
                f"|KP|={result['mean_abs_kp_t']:.2f} "
                f"sig BMP={result['share_significant_bmp']:.1%} "
                f"sig KP={result['share_significant_kp']:.1%} "
                f"pooled t={pooled['t_naive']} -> {pooled['t_kp']}"
            )
        else:
            print(f"{dataset:14s} no priced events")

    path = ROOT / "docs" / "results" / "kp_test.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
