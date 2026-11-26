"""Regenerate the benchmark summaries under docs/results/.

The event-level detail is excluded from the JSON summaries; it is available
from the API and is reproducible from the same config.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.backtest import BacktestEngine
from backend.app.schemas import BacktestConfig

CONFIGS = [
    ("curated_1d", BacktestConfig(dataset="curated", window_end=1)),
    ("curated_5d", BacktestConfig(dataset="curated", window_end=5)),
    ("fomc_1d", BacktestConfig(dataset="fomc", window_end=1)),
    ("fomc_surprise_1d", BacktestConfig(dataset="fomc_surprise", window_end=1)),
    ("extended_1d", BacktestConfig(dataset="extended", window_end=1)),
]


def main() -> None:
    out = ROOT / "docs" / "results"
    out.mkdir(parents=True, exist_ok=True)
    for name, config in CONFIGS:
        result = BacktestEngine(config=config).run(config)
        payload = result.model_dump(mode="json", exclude={"events"})
        payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path = out / f"backtest_{name}_summary.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            f"{name:18s} events={result.n_events:3d} "
            f"models={len(result.metrics):2d} -> {path.name}"
        )


if __name__ == "__main__":
    main()
