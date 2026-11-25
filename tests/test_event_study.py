from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from backend.app.evaluation.event_study import compute_outcomes, event_day_index
from backend.app.schemas import BacktestConfig, Direction, EventType, LabeledEvent, SourceRef


def _prices() -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=300)
    market = 0.001 + 0.0001 * np.sin(np.arange(300))
    market[200] = 0.001
    asset = 0.0005 + 1.5 * market
    asset[200] += 0.0020
    asset[201] += 0.0030
    frame = pd.DataFrame(
        {
            "SPY": (1 + market).cumprod() * 100,
            "QQQ": (1 + asset).cumprod() * 100,
        },
        index=index,
    )
    return frame


def _event(day: date, session: str = "during") -> LabeledEvent:
    return LabeledEvent(
        id="test-event",
        headline="Fed raises rates by 50 basis points",
        published_at=datetime(day.year, day.month, day.day, 14, 0, tzinfo=timezone.utc),
        source=SourceRef(name="test"),
        event_type=EventType.MONETARY_POLICY,
        direction=Direction.TIGHTENING,
        gold_event_type=EventType.MONETARY_POLICY,
        gold_direction=Direction.TIGHTENING,
        confidence=0.9,
        session=session,
    )


def test_market_model_recovers_known_abnormal_return():
    prices = _prices()
    day = prices.index[200].date()
    outcomes, skipped = compute_outcomes(
        [_event(day)],
        prices,
        ["SPY", "QQQ"],
        BacktestConfig(window_end=0, estimation_start=-120, estimation_end=-21, flat_threshold_bps=1),
    )
    assert skipped == []
    qqq = outcomes["test-event"]["QQQ"]
    assert qqq.beta == pytest.approx(1.5, abs=0.05)
    assert qqq.car == pytest.approx(0.0020, abs=1e-6)
    assert qqq.direction == "up"


def test_market_asset_uses_raw_return():
    prices = _prices()
    day = prices.index[200].date()
    outcomes, _ = compute_outcomes(
        [_event(day)],
        prices,
        ["SPY"],
        BacktestConfig(window_end=0, estimation_start=-120, estimation_end=-21, flat_threshold_bps=1),
    )
    spy = outcomes["test-event"]["SPY"]
    assert spy.car == pytest.approx(0.0010, abs=1e-6)


def test_after_close_aligns_to_next_trading_day():
    prices = _prices()
    day = prices.index[200].date()
    outcomes, _ = compute_outcomes(
        [_event(day, session="after_close")],
        prices,
        ["QQQ"],
        BacktestConfig(window_end=0, estimation_start=-120, estimation_end=-21, flat_threshold_bps=1),
    )
    qqq = outcomes["test-event"]["QQQ"]
    assert qqq.event_day == prices.index[201].date()
    assert qqq.car == pytest.approx(0.0030, abs=1e-6)


def test_event_day_index_for_weekend_uses_next_session():
    days = list(pd.bdate_range("2024-01-01", periods=10))
    # 2024-01-06 is a Saturday.
    assert event_day_index(days, date(2024, 1, 6), "non_trading") == 5
    assert event_day_index(days, date(2024, 1, 6), "during") == 5
