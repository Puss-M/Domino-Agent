from __future__ import annotations

import tempfile
from pathlib import Path


from backend.app.schemas import (
    Direction,
    EventType,
    MacroEvent,
    Magnitude,
    SourceRef,
)
from backend.app.symbolic import (
    AuditLedger,
    InfluenceGraph,
    PolicyEngine,
    Sign,
    SMTCertifier,
    SymbolicVerifier,
    combine,
    mul,
    to_turtle,
    validate_event_units,
)
from backend.app.symbolic.signs import from_number


def _event() -> MacroEvent:
    from datetime import datetime, timezone

    return MacroEvent(
        id="test",
        headline="Fed raises rates by 50 basis points",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        source=SourceRef(name="test"),
        event_type=EventType.MONETARY_POLICY,
        direction=Direction.TIGHTENING,
        actor="US_FED",
        magnitude=Magnitude(value=50, unit="bps"),
        confidence=0.9,
    )


# --------------------------------------------------------------------- signs
def test_sign_multiplication():
    assert mul(Sign.POS, Sign.POS) is Sign.POS
    assert mul(Sign.POS, Sign.NEG) is Sign.NEG
    assert mul(Sign.NEG, Sign.NEG) is Sign.POS
    assert mul(Sign.ZERO, Sign.POS) is Sign.ZERO
    assert mul(Sign.AMBIGUOUS, Sign.POS) is Sign.AMBIGUOUS


def test_sign_combination():
    assert combine([Sign.POS, Sign.POS]) is Sign.POS
    assert combine([Sign.NEG, Sign.NEG]) is Sign.NEG
    assert combine([Sign.POS, Sign.NEG]) is Sign.AMBIGUOUS
    assert combine([]) is Sign.ZERO
    assert combine([Sign.ZERO, Sign.POS]) is Sign.POS


def test_sign_from_number():
    assert from_number(0.5) is Sign.POS
    assert from_number(-0.5) is Sign.NEG
    assert from_number(0.0) is Sign.ZERO


# --------------------------------------------------------------------- graph
def test_influence_graph_is_acyclic_and_finds_paths(knowledge):
    from backend.app.knowledge.retrieval import MechanismRetriever

    event = _event()
    matches = MechanismRetriever(knowledge).match(event)
    assets = ["SPY", "QQQ", "TLT", "GLD"]
    graph = InfluenceGraph.from_matches(matches, knowledge.channels, assets)
    acyclic, cycles = graph.is_acyclic()
    assert acyclic
    assert cycles == []
    assert graph.paths("event", "asset:SPY")
    views = graph.qualitative_views(assets)
    assert views["QQQ"].sign is Sign.NEG
    assert views["SPY"].sign is Sign.NEG


def test_qualitative_ambiguity_is_first_class(knowledge):
    from backend.app.knowledge.retrieval import MechanismRetriever

    event = _event()
    matches = MechanismRetriever(knowledge).match(event)
    graph = InfluenceGraph.from_matches(matches, knowledge.channels, ["TLT", "GLD"])
    views = graph.qualitative_views(["TLT", "GLD"])
    # Duration falls on higher yields, but the risk-premium/safe-haven path
    # supports bonds; pure signs cannot resolve it.
    assert views["TLT"].sign is Sign.AMBIGUOUS
    assert views["TLT"].conflicts
    assert "ambiguous" in views["TLT"].explanation.lower()


# ----------------------------------------------------------------------- SMT
def test_smt_proves_a_direction_and_returns_core(knowledge):
    from backend.app.knowledge.retrieval import MechanismRetriever

    event = _event()
    matches = MechanismRetriever(knowledge).match(event)
    certifier = SMTCertifier(matches, knowledge.channels, ["SPY", "QQQ", "TLT"])
    result = certifier.certify("QQQ", Sign.NEG)
    assert result.status.value == "proved"
    assert result.core == ["MON_TIGHTEN"]


def test_smt_reports_ambiguity(knowledge):
    from backend.app.knowledge.retrieval import MechanismRetriever

    event = _event()
    matches = MechanismRetriever(knowledge).match(event)
    certifier = SMTCertifier(matches, knowledge.channels, ["TLT"])
    result = certifier.certify("TLT", Sign.NEG)
    assert result.status.value in {"ambiguous", "not_entailed"}


def test_smt_without_mechanisms_is_not_entailed(knowledge):
    certifier = SMTCertifier([], knowledge.channels, ["SPY"])
    result = certifier.certify("SPY", Sign.NEG)
    assert result.status.value == "not_entailed"


# ------------------------------------------------------------------ ontology
def test_unit_validation():
    event = _event()
    assert validate_event_units(event) == []
    bad = event.model_copy(deep=True)
    bad.magnitude = Magnitude(value=50, unit="usd_bn")
    issues = validate_event_units(bad)
    assert issues and "dimension" in issues[0]


def test_turtle_export_has_mechanisms(knowledge):
    ttl = to_turtle(knowledge)
    assert "domino:Mechanism" in ttl
    assert "domino:mechanism_MON_TIGHTEN" in ttl
    assert "dct:source" in ttl


# -------------------------------------------------------------------- policy
def test_policy_engine_passes_clean_output(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    results = PolicyEngine().evaluate(response, response.symbolic)
    failures = [r for r in results if not r.passed and r.severity == "error"]
    assert failures == []
    assert response.symbolic.ledger_hash


def test_policy_catches_injected_hallucination(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    hallucinated = response.model_copy(deep=True)
    hallucinated.memo.summary = (
        "SPY will fall 3.2% and gold will rally 12.5%; we recommend you buy gold "
        "with 95.7% confidence."
    )
    results = PolicyEngine().evaluate(hallucinated, hallucinated.symbolic)
    failed = {r.id for r in results if not r.passed}
    assert "P-002" in failed  # advice language
    assert "P-004" in failed  # untraceable numbers


# -------------------------------------------------------------------- ledger
def test_policy_catches_fake_mechanism_id(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    bad = response.model_copy(deep=True)
    bad.memo.summary += " The effect is driven by MON_FAKE_001."
    results = PolicyEngine(knowledge=engine.knowledge).evaluate(bad, bad.symbolic)
    assert any(r.id == "P-010" and not r.passed for r in results)


def test_policy_catches_fake_citation(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    bad = response.model_copy(deep=True)
    bad.memo.citations.append("Smith (2030), Journal of Fabricated Results.")
    results = PolicyEngine(knowledge=engine.knowledge).evaluate(bad, bad.symbolic)
    assert any(r.id == "P-011" and not r.passed for r in results)


def test_policy_catches_fake_asset(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    bad = response.model_copy(deep=True)
    bad.memo.asset_views.append("AMZN: up, P(up)=0.9")
    results = PolicyEngine(knowledge=engine.knowledge).evaluate(bad, bad.symbolic)
    assert any(r.id == "P-012" and not r.passed for r in results)


def test_policy_catches_right_number_wrong_unit(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    bad = response.model_copy(deep=True)
    bad.memo.summary += " The move was 50 percent."
    results = PolicyEngine().evaluate(bad, bad.symbolic)
    assert any(r.id == "P-013" and not r.passed for r in results)
    # The value itself is grounded, so P-004 should not be the one catching it.
    assert all(r.passed for r in results if r.id == "P-004")


def test_policy_catches_numeric_direction_contradicting_a_proof(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    proof = next(
        (
            item
            for item in response.symbolic.proofs
            if item.status == "proved" and item.claim in {"+", "-"}
        ),
        None,
    )
    assert proof is not None
    expected_opposite = "down" if proof.claim == "+" else "up"
    bad = response.model_copy(deep=True)
    for prediction in bad.predictions:
        if prediction.asset == proof.asset:
            prediction.direction = expected_opposite
            prediction.abstain = False
            break
    results = PolicyEngine().evaluate(bad, bad.symbolic)
    assert any(r.id == "P-008" and not r.passed for r in results)


def test_audit_ledger_hash_chain():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = AuditLedger(path=Path(tmp) / "ledger.jsonl")
        first = ledger.append({"event": "a", "value": 1})
        second = ledger.append({"event": "b", "value": 2})
        assert first["prev_hash"] == "GENESIS"
        assert second["prev_hash"] == first["hash"]
        assert ledger.verify_chain()


def test_engine_attaches_symbolic_report(engine):
    response = engine.analyze_headline("Fed raises rates by 50 basis points")
    assert response.symbolic is not None
    assert response.symbolic.node_count > 0
    assert response.symbolic.acyclic
    assert response.symbolic.proofs
    assert response.symbolic.policy_results
    assert response.symbolic.ledger_hash
    assert any(p.status == "proved" for p in response.symbolic.proofs)
    assert any(p.status == "ambiguous" for p in response.symbolic.proofs)


def test_symbolic_verifier_reports_coverage(knowledge):
    from backend.app.knowledge.retrieval import MechanismRetriever
    from backend.app.reasoning.transmission import TransmissionModel

    event = _event()
    matches = MechanismRetriever(knowledge).match(event)
    transmission = TransmissionModel(knowledge, assets=["SPY", "QQQ", "TLT"]).build(event, matches)
    report = SymbolicVerifier(knowledge).verify(event, matches, transmission.predictions)
    assert 0.0 <= report.proof_coverage <= 1.0
    assert report.node_count > 0
    assert report.edge_count > 0
