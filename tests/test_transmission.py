from __future__ import annotations

from backend.app.reasoning.engine import AnalysisEngine


def _by_asset(response):
    return {prediction.asset: prediction for prediction in response.predictions}


def test_hawkish_hike_transmission(engine: AnalysisEngine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    assets = _by_asset(response)
    assert assets["QQQ"].p_up < 0.5
    assert assets["TLT"].p_up < 0.5
    assert assets["UUP"].p_up > 0.5
    assert assets["^VIX"].p_up > 0.5
    assert assets["QQQ"].mechanisms == ["MON_TIGHTEN"]
    assert response.audit.passed


def test_emergency_cut_is_not_risk_on(engine: AnalysisEngine):
    response = engine.analyze_headline("Fed cuts rates by 50 basis points in emergency move")
    assets = _by_asset(response)
    assert assets["SPY"].p_up < 0.5
    assert assets["TLT"].p_up > 0.5
    assert assets["^VIX"].p_up > 0.5
    assert "MON_EASE_STRESS" in assets["SPY"].mechanisms


def test_china_stimulus_is_positive_for_china_equities(engine: AnalysisEngine):
    response = engine.analyze_headline(
        "China unveils a stimulus package and cuts the reserve requirement ratio"
    )
    assets = _by_asset(response)
    assert assets["FXI"].p_up > 0.5
    assert assets["EEM"].p_up > 0.5
    assert "CHINA_STIMULUS" in assets["FXI"].mechanisms


def test_unknown_event_abstains(engine: AnalysisEngine):
    response = engine.analyze_headline("A company appoints a new marketing director")
    assert all(prediction.abstain for prediction in response.predictions)
    assert all(prediction.p_up == 0.5 for prediction in response.predictions)
    assert not response.audit.passed
    assert len(response.graph.edges) == 0


def test_graph_edges_are_cited_and_nonzero(engine: AnalysisEngine):
    response = engine.analyze_headline("US CPI rises 3.5% in March, above expectations")
    assert response.graph.nodes
    assert response.graph.edges
    for edge in response.graph.edges:
        assert edge.sign in {-1, 1}
        assert edge.citations
        assert edge.mechanism_id.startswith(("MON", "INFL", "TRADE", "OIL", "GEO", "CHINA", "FISCAL", "BANK", "BOJ", "ECB"))


def test_edge_sign_reflects_net_effect_not_raw_loading(engine: AnalysisEngine):
    response = engine.analyze_headline(
        "China unveils a stimulus package and cuts the reserve requirement ratio"
    )
    usd_to_uup = [
        edge
        for edge in response.graph.edges
        if edge.source == "channel:usd" and edge.target == "asset:UUP"
    ]
    assert usd_to_uup
    # The dollar channel falls, and UUP loads positively on it: the effect is negative.
    assert all(edge.sign == -1 for edge in usd_to_uup)

    risk_to_spy = [
        edge
        for edge in response.graph.edges
        if edge.source == "channel:risk_premium" and edge.target == "asset:SPY"
    ]
    assert risk_to_spy
    # Risk premia fall, and SPY loads negatively on them: the effect is positive.
    assert all(edge.sign == 1 for edge in risk_to_spy)


def test_asset_probabilities_are_bounded(engine: AnalysisEngine):
    response = engine.analyze_headline("OPEC+ announces a 2 million barrels per day production cut")
    for prediction in response.predictions:
        assert 0.0 <= prediction.p_up <= 1.0
        assert -1500 <= prediction.expected_car_bps <= 1500
