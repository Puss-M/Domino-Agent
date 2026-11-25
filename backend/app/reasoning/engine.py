"""The orchestrated analysis pipeline.

    news text
      -> rule-first event extraction
      -> cited mechanism retrieval
      -> deterministic channel/asset transmission
      -> evidence audit
      -> template memo

No network call is required for the offline path. Optional connectors enrich
the input; they never silently change the reasoning graph.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import Settings, get_settings
from ..knowledge.loader import KnowledgeBase, load_knowledge
from ..knowledge.retrieval import MechanismRetriever
from ..nlp.extractor import EventExtractor
from ..schemas import (
    AnalysisResponse,
    BatchAnalyzeRequest,
    LabeledEvent,
    NewsItem,
    PolicyResult,
    Provenance,
    SourceRef,
    SourceTier,
)
from ..symbolic import AuditLedger, PolicyEngine, SymbolicVerifier
from .audit import audit
from .memo import MemoBuilder
from .transmission import TransmissionModel


class AnalysisEngine:
    def __init__(
        self,
        settings: Settings | None = None,
        knowledge: KnowledgeBase | None = None,
        assets: list[str] | None = None,
    ):
        self.settings = settings or get_settings()
        self.knowledge = knowledge or load_knowledge(settings=self.settings)
        self.extractor = EventExtractor()
        self.retriever = MechanismRetriever(self.knowledge)
        self.transmission = TransmissionModel(self.knowledge, assets=assets)
        self.memo_builder = MemoBuilder(self.knowledge)
        self.symbolic = SymbolicVerifier(self.knowledge, self.settings)
        self.policy_engine = PolicyEngine()
        self.ledger = AuditLedger(self.settings)

    def analyze_news(
        self,
        news: NewsItem,
        *,
        as_of: datetime | None = None,
    ) -> AnalysisResponse:
        event, extraction_debug = self.extractor.extract_with_debug(news)
        matches = self.retriever.match(event)
        transmission = self.transmission.build(event, matches)
        audit_report = audit(event, matches, transmission, as_of=as_of)
        memo = self.memo_builder.build(event, matches, transmission)

        provenance = Provenance(
            sources=[
                f"event source: {news.source_name} ({news.source_tier.value})",
                f"extraction: {event.extraction_method}",
                f"mechanism library: {self.knowledge.path.name} v{self.knowledge.version}",
                "transmission: deterministic channel/loading model",
            ],
            retrieved_at=datetime.now(timezone.utc),
            as_of=as_of or event.published_at,
            notes=[
                "Mechanism signs and loadings are expert priors authored in the library, not estimates fitted to this event.",
                "Expected CAR is an order-of-magnitude prior; it is not a price target or a trading signal.",
                "No LLM is used in the offline path; numeric and graphical outputs are deterministic.",
            ],
        )
        response = AnalysisResponse(
            event=event,
            graph=transmission.graph,
            channel_activations=list(transmission.channels.values()),
            predictions=transmission.predictions,
            memo=memo,
            audit=audit_report,
            provenance=provenance,
            diagnostics={
                "extraction": extraction_debug,
                "retrieval": self.retriever.evaluate(event),
                "transmission": transmission.diagnostics,
                "audit_issues": audit_report.issues,
                "audit_warnings": audit_report.warnings,
            },
        )

        # Symbolic layer: sign algebra + SMT certification + policy-as-code.
        symbolic_report = self.symbolic.verify(event, matches, transmission.predictions)
        response.symbolic = symbolic_report
        policy_results: list[PolicyResult] = self.policy_engine.evaluate(response, symbolic_report)
        symbolic_report.policy_results = policy_results
        policy_errors = [result for result in policy_results if not result.passed and result.severity == "error"]
        if policy_errors:
            audit_report.passed = False
            audit_report.issues = list(audit_report.issues) + [
                f"{result.id}: {result.detail}" for result in policy_errors
            ]
        payload = response.model_dump(mode="json")
        if payload.get("symbolic"):
            payload["symbolic"].pop("ledger_hash", None)
        record = self.ledger.append(payload)
        symbolic_report.ledger_hash = record["hash"]
        response.diagnostics["symbolic"] = {
            "proof_coverage": symbolic_report.proof_coverage,
            "policy_failures": [r.id for r in policy_results if not r.passed],
            "ledger_hash": record["hash"],
        }
        return response

    def analyze_headline(
        self,
        headline: str,
        *,
        summary: str = "",
        published_at: datetime | None = None,
        source_name: str = "user",
        source_url: str | None = None,
        source_tier: SourceTier = SourceTier.MEDIA,
        as_of: datetime | None = None,
    ) -> AnalysisResponse:
        published = published_at or datetime.now(timezone.utc)
        news = NewsItem(
            title=headline,
            summary=summary,
            url=source_url,
            source_name=source_name,
            source_tier=source_tier,
            published_at=published,
        )
        return self.analyze_news(news, as_of=as_of or published)

    def analyze_labeled(self, event: LabeledEvent) -> AnalysisResponse:
        news = NewsItem(
            id=event.id,
            title=event.headline,
            summary=event.summary,
            url=event.source.url,
            source_name=event.source.name,
            source_tier=event.source.tier,
            published_at=event.published_at,
        )
        return self.analyze_news(news, as_of=event.published_at)

    def analyze_batch(self, request: BatchAnalyzeRequest) -> list[AnalysisResponse]:
        responses = []
        for item in request.items:
            responses.append(
                self.analyze_headline(
                    item.headline,
                    summary=item.summary,
                    published_at=item.published_at,
                    source_name=item.source_name,
                    source_url=item.source_url,
                    source_tier=item.source_tier,
                )
            )
        return responses

    def source_ref(self, news: NewsItem) -> SourceRef:
        return SourceRef(
            name=news.source_name,
            url=news.url,
            tier=news.source_tier,
            published_at=news.published_at,
        )
