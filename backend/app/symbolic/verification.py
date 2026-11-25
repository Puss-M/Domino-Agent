"""Orchestrate the symbolic layer over a numeric transmission result."""

from __future__ import annotations

from ..config import Settings, get_settings
from ..knowledge.loader import KnowledgeBase
from ..schemas import (
    AssetPrediction,
    MacroEvent,
    MechanismMatch,
    ProofReport,
    QualitativeAssetView,
    SymbolicReport,
)
from .graph import InfluenceGraph
from .ontology import validate_event_units
from .signs import Sign
from .smt import ProofStatus, SMTCertifier


class SymbolicVerifier:
    def __init__(self, knowledge: KnowledgeBase, settings: Settings | None = None):
        self.knowledge = knowledge
        self.settings = settings or get_settings()

    def verify(
        self,
        event: MacroEvent,
        matches: list[MechanismMatch],
        predictions: list[AssetPrediction],
        *,
        certify: bool = True,
    ) -> SymbolicReport:
        assets = [prediction.asset for prediction in predictions]
        graph = InfluenceGraph.from_matches(matches, self.knowledge.channels, assets)
        views = graph.qualitative_views(assets)
        acyclic, cycles = graph.is_acyclic()

        certifier = SMTCertifier(matches, self.knowledge.channels, assets) if certify else None
        proofs: list[ProofReport] = []
        for asset in assets:
            view = views[asset]
            prediction = next((p for p in predictions if p.asset == asset), None)
            if view.sign is Sign.AMBIGUOUS:
                proofs.append(
                    ProofReport(
                        asset=asset,
                        claim="?",
                        status=ProofStatus.AMBIGUOUS.value,
                        core=[],
                        paths=[path.readable for path in view.paths],
                        note=view.explanation,
                    )
                )
                continue
            if view.sign is Sign.ZERO:
                proofs.append(
                    ProofReport(
                        asset=asset,
                        claim="0",
                        status=ProofStatus.NOT_ENTAILED.value,
                        core=[],
                        paths=[path.readable for path in view.paths],
                        note="No net directional effect from the cited paths.",
                    )
                )
                continue
            if certifier is None:
                proofs.append(
                    ProofReport(
                        asset=asset,
                        claim=view.sign.value,
                        status=ProofStatus.UNVERIFIED.value,
                        core=[],
                        paths=[path.readable for path in view.paths],
                        note="Certification disabled.",
                    )
                )
                continue
            result = certifier.certify(asset, view.sign)
            # A definite qualitative view that the solver cannot prove is a
            # contradiction worth surfacing, not a silent pass.
            if result.status is ProofStatus.NOT_ENTAILED and prediction and not prediction.abstain:
                result.note += " (numeric prediction was not abstaining)"
            proofs.append(
                ProofReport(
                    asset=asset,
                    claim=result.claim,
                    status=result.status.value,
                    core=result.core,
                    paths=result.paths,
                    note=result.note,
                )
            )

        active = [p for p in predictions if not p.abstain]
        proved = [
            proof
            for proof in proofs
            if proof.status == ProofStatus.PROVED.value
            and any(p.asset == proof.asset for p in active)
        ]
        coverage = round(len(proved) / len(active), 4) if active else 0.0
        qualitative = [
            QualitativeAssetView(**views[asset].to_dict()) for asset in assets
        ]
        return SymbolicReport(
            node_count=graph.node_count,
            edge_count=graph.edge_count,
            acyclic=acyclic,
            cycles=cycles,
            qualitative=qualitative,
            proofs=proofs,
            ontology_issues=validate_event_units(event),
            proof_coverage=coverage,
        )
