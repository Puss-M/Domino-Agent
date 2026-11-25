from __future__ import annotations

import pytest

from backend.app.nlp.numbers import best_magnitude, detect_surprise, parse_numbers, surprise_scale


def test_basis_points():
    parsed = parse_numbers("The Fed raised rates by 50 basis points")
    assert parsed[0].unit == "bps"
    assert parsed[0].value == 50


def test_percentage_points_vs_percent():
    parsed = parse_numbers("CPI rose 0.3 percentage points, or 8.6% year over year")
    units = [item.unit for item in parsed]
    assert "pp" in units
    assert "pct" in units


def test_trillion_normalised_to_billion():
    parsed = parse_numbers("A $1.9 trillion package")
    assert parsed[0].unit == "usd_bn"
    assert parsed[0].value == pytest.approx(1900.0)


def test_million_barrels_per_day():
    parsed = parse_numbers("OPEC+ will cut 2 million barrels per day")
    assert parsed[0].unit == "mbpd"
    assert parsed[0].value == pytest.approx(2.0)


def test_chinese_units():
    parsed = parse_numbers("美联储加息50个基点，规模达200万桶/日")
    units = {item.unit for item in parsed}
    assert "bps" in units
    assert "mbpd" in units


def test_best_magnitude_prefers_rate_units():
    magnitude = best_magnitude("The ECB raised rates by 0.5 percentage points", "monetary_policy")
    assert magnitude is not None
    assert magnitude.unit == "pp"
    assert magnitude.value == pytest.approx(0.5)


def test_surprise_hot_and_cool_are_both_positive():
    hot = detect_surprise("CPI came in hotter than expected")
    cool = detect_surprise("CPI came in cooler than expected")
    assert hot.sign == "positive"
    assert cool.sign == "positive"


def test_surprise_vs_consensus_value():
    surprise = detect_surprise("CPI at 3.5% vs 3.4% expected")
    assert surprise.unit == "pp"
    assert surprise.value == pytest.approx(0.1)
    assert surprise.sign == "positive"


def test_surprise_in_line_is_neutral():
    surprise = detect_surprise("The Fed hike was in line with expectations")
    assert surprise.sign == "neutral"


def test_surprise_scale_is_bounded():
    hot = detect_surprise("CPI at 9.1% vs 8.8% expected")
    assert 0.5 <= surprise_scale("inflation", hot, None) <= 2.0
