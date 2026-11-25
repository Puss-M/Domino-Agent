"""Command-line interface for offline analysis and evaluation.

Examples:
    python -m backend.app.cli analyze "Fed raises rates by 50 basis points"
    python -m backend.app.cli backtest --window-end 1 --out backtest.json
    python -m backend.app.cli sources
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluation.backtest import BacktestEngine
from .evaluation.dataset import load_events
from .reasoning.engine import AnalysisEngine
from .schemas import BacktestConfig


def _print_json(payload) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def cmd_analyze(args: argparse.Namespace) -> int:
    engine = AnalysisEngine()
    response = engine.analyze_headline(
        args.headline,
        summary=args.summary,
        source_name=args.source,
    )
    if args.json:
        _print_json(response)
        return 0
    event = response.event
    print(f"\nDomino Agent — {event.headline}\n")
    print(f"event:      {event.event_type.value} / {event.direction.value}")
    print(f"actor:      {event.actor or '—'}")
    print(f"magnitude:  {event.magnitude.model_dump() if event.magnitude else '—'}")
    print(f"surprise:   {event.surprise.model_dump() if event.surprise else '—'}")
    print(f"confidence: {event.confidence:.2f}")
    print("\nchannels")
    for activation in response.channel_activations:
        print(f"  {activation.name:32s} {activation.score:+.2f}")
    print("\nassets (prior, 5d)")
    for prediction in response.predictions[:8]:
        print(
            f"  {prediction.asset:5s} {prediction.direction:4s} "
            f"P(up)={prediction.p_up:.2f}  {prediction.expected_car_bps:+7.0f}bp  "
            f"grade={prediction.evidence_grade.value}"
            + ("  ABSTAIN" if prediction.abstain else "")
        )
    print("\nmemo")
    print(response.memo.summary)
    if response.audit.issues:
        print("\naudit issues")
        for issue in response.audit.issues:
            print(f"  - {issue}")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    config = BacktestConfig(window_end=args.window_end, bootstrap_samples=args.bootstrap)
    result = BacktestEngine(config=config).run(config)
    if args.out:
        Path(args.out).write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote {args.out}")
    if args.json:
        _print_json(result)
        return 0
    print(f"\nBacktest: {result.n_events} events, {result.n_outcome_observations} outcome observations")
    print(f"window: 0..{result.config.window_end} trading days\n")
    print(f"{'model':32s} {'n':>4s} {'cov':>6s} {'acc':>7s} {'brier':>7s} {'auc':>7s} {'ece':>7s}")
    for metric in result.metrics:
        print(
            f"{metric.model:32s} {metric.n:4d} {metric.coverage:6.3f} "
            f"{_fmt(metric.accuracy):>7s} {_fmt(metric.brier):>7s} "
            f"{_fmt(metric.auc):>7s} {_fmt(metric.ece):>7s}"
        )
    print("\nextraction:", result.extraction.model_dump())
    print("\nnotes:")
    for note in result.notes:
        print(f"  - {note}")
    return 0


def _fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def cmd_sources(_args: argparse.Namespace) -> int:
    from .datasources import DATA_SOURCES

    for source in DATA_SOURCES:
        print(f"{source.id:10s} {source.name}")
        print(f"           access={source.access}; PIT={source.point_in_time}")
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    events = load_events()
    if args.json:
        _print_json([event.model_dump(mode="json") for event in events])
        return 0
    print(f"{len(events)} events")
    for event in events:
        print(
            f"{event.published_at.date()}  {event.event_type.value:18s} "
            f"{event.direction.value:14s} {event.headline}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="domino", description="Domino Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="analyze one headline")
    analyze.add_argument("headline")
    analyze.add_argument("--summary", default="")
    analyze.add_argument("--source", default="user")
    analyze.add_argument("--json", action="store_true")
    analyze.set_defaults(func=cmd_analyze)

    backtest = sub.add_parser("backtest", help="run the walk-forward event study")
    backtest.add_argument("--window-end", type=int, default=1)
    backtest.add_argument("--bootstrap", type=int, default=500)
    backtest.add_argument("--out", default="")
    backtest.add_argument("--json", action="store_true")
    backtest.set_defaults(func=cmd_backtest)

    sources = sub.add_parser("sources", help="list data sources")
    sources.set_defaults(func=cmd_sources)

    events = sub.add_parser("events", help="list the curated event sample")
    events.add_argument("--json", action="store_true")
    events.set_defaults(func=cmd_events)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
