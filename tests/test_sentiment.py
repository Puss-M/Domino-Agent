from __future__ import annotations

from backend.app.nlp.sentiment import FinancialSentiment


def test_positive_and_negative_financial_tone():
    sentiment = FinancialSentiment()
    assert sentiment.score("The company beat expectations and raised guidance").polarity > 0
    assert sentiment.score("The company missed expectations and cut guidance").polarity < 0


def test_negation_flips_polarity():
    sentiment = FinancialSentiment()
    plain = sentiment.score("The outlook is strong").polarity
    negated = sentiment.score("The outlook is not strong").polarity
    assert plain > 0
    assert negated < 0


def test_hawkish_language():
    sentiment = FinancialSentiment()
    result = sentiment.score("The Fed remains hawkish and signals higher for longer")
    assert result.hawkish > 0


def test_dovish_language():
    sentiment = FinancialSentiment()
    result = sentiment.score("The central bank is dovish and signals rate cuts")
    assert result.dovish > 0


def test_uncertainty_is_separate_from_polarity():
    sentiment = FinancialSentiment()
    result = sentiment.score("The outlook is uncertain and the path may change")
    assert result.uncertainty > 0


def test_chinese_hawkish_terms():
    sentiment = FinancialSentiment()
    result = sentiment.score("美联储加息，鹰派信号明显")
    assert result.hawkish > 0


def test_crisis_raises_risk_off():
    sentiment = FinancialSentiment()
    calm = sentiment.score("Markets are stable")
    crisis = sentiment.score("A banking crisis and a bank run are spreading")
    assert crisis.risk_off > calm.risk_off
