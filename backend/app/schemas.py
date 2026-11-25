"""Typed contracts shared by the API, the reasoning engine and the evaluator."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    MONETARY_POLICY = "monetary_policy"
    INFLATION = "inflation"
    LABOR_MARKET = "labor_market"
    TRADE_POLICY = "trade_policy"
    ENERGY_SUPPLY = "energy_supply"
    GEOPOLITICS = "geopolitics"
    FINANCIAL_STABILITY = "financial_stability"
    FISCAL_POLICY = "fiscal_policy"
    CHINA_POLICY = "china_policy"
    OTHER = "other"


class Direction(str, Enum):
    TIGHTENING = "tightening"
    EASING = "easing"
    HAWKISH_HOLD = "hawkish_hold"
    DOVISH_HOLD = "dovish_hold"
    UPSIDE = "upside"
    DOWNSIDE = "downside"
    ESCALATION = "escalation"
    DEESCALATION = "deescalation"
    SUPPLY_CUT = "supply_cut"
    SUPPLY_INCREASE = "supply_increase"
    RISK_OFF = "risk_off"
    RISK_ON = "risk_on"
    STRESS = "stress"
    STIMULUS = "stimulus"
    NEUTRAL = "neutral"


class EvidenceGrade(str, Enum):
    A = "A"  # peer-reviewed / official mechanism, conditions met
    B = "B"  # empirical support, condition uncertainty
    C = "C"  # plausible but weak evidence
    D = "D"  # speculative, never used for a headline prediction


class SourceTier(str, Enum):
    OFFICIAL = "official"
    PRIMARY = "primary"
    WIRE = "wire"
    MEDIA = "media"
    RESEARCH = "research"
    MODEL = "model"


class Magnitude(BaseModel):
    value: float
    unit: Literal["bps", "pp", "pct", "usd_bn", "usd", "mbpd", "index", "count", "qualitative"]
    raw: str = ""
    note: str = ""


class Surprise(BaseModel):
    value: float = 0.0
    unit: Literal["bps", "pp", "pct", "qualitative"] = "qualitative"
    sign: Literal["positive", "negative", "neutral"] = "neutral"
    raw: str = ""
    note: str = ""


class SourceRef(BaseModel):
    name: str
    url: str | None = None
    tier: SourceTier = SourceTier.MEDIA
    published_at: datetime | None = None
    retrieved_at: datetime | None = None


class NewsItem(BaseModel):
    id: str | None = None
    title: str
    summary: str = ""
    url: str | None = None
    source_name: str = "user"
    source_tier: SourceTier = SourceTier.MEDIA
    published_at: datetime
    language: str = "en"
    entities: list[str] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}".strip()


class MacroEvent(BaseModel):
    id: str
    headline: str
    summary: str = ""
    published_at: datetime
    source: SourceRef
    event_type: EventType
    direction: Direction
    actor: str | None = None
    magnitude: Magnitude | None = None
    surprise: Surprise | None = None
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: str = "rules-v1"
    text_sentiment: dict[str, float] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def _bounded(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class ChannelSpec(BaseModel):
    id: str
    name: str
    description: str
    loadings: dict[str, float]
    scale_bps: float = 120.0
    citations: list[str] = Field(default_factory=list)

    @field_validator("loadings")
    @classmethod
    def _bounded_loadings(cls, value: dict[str, float]) -> dict[str, float]:
        for asset, loading in value.items():
            if abs(loading) > 1.5:
                raise ValueError(f"loading for {asset} looks like a sign/weight, not an elasticity")
        return value


class MechanismSpec(BaseModel):
    id: str
    title: str
    event_types: list[EventType]
    directions: list[Direction] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    any_keywords: list[str] = Field(default_factory=list)
    none_keywords: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_grade: EvidenceGrade
    horizon_days: int = 5
    rationale: str
    channels: dict[str, float]
    citations: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("channels")
    @classmethod
    def _channel_weights(cls, value: dict[str, float]) -> dict[str, float]:
        for channel, weight in value.items():
            if not -1.5 <= weight <= 1.5:
                raise ValueError(f"channel weight for {channel} must be in [-1.5, 1.5]")
        return value


class MechanismMatch(BaseModel):
    mechanism: MechanismSpec
    score: float
    matched_keywords: list[str] = Field(default_factory=list)
    conditions_met: bool = True


class ChannelActivation(BaseModel):
    channel: str
    name: str
    score: float
    contributions: list[dict[str, Any]] = Field(default_factory=list)


class AssetPrediction(BaseModel):
    asset: str
    label: str
    direction: Literal["up", "down", "flat"]
    p_up: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    expected_car_bps: float
    horizon_days: int
    evidence_grade: EvidenceGrade
    abstain: bool = False
    channels: list[str] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    rationale: str = ""
    conflicting: bool = False


class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["event", "channel", "asset"]
    layer: int
    confidence: float = 0.0
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    sign: int
    weight: float
    mechanism_id: str
    channel: str
    evidence_grade: EvidenceGrade
    rationale: str
    citations: list[str] = Field(default_factory=list)


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Memo(BaseModel):
    title: str
    summary: str
    transmission: list[str] = Field(default_factory=list)
    asset_views: list[str] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)
    monitoring: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Research prototype. This is a transmission hypothesis calibrated on a small "
        "historical sample, not investment advice or an identified causal effect."
    )


class Provenance(BaseModel):
    sources: list[str] = Field(default_factory=list)
    retrieved_at: datetime | None = None
    as_of: datetime | None = None
    snapshot_version: str = "local"
    notes: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_edges: int = 0
    used_mechanisms: list[str] = Field(default_factory=list)


class PolicyResult(BaseModel):
    id: str
    title: str
    passed: bool
    severity: Literal["error", "warning", "info"] = "error"
    detail: str = ""


class ProofReport(BaseModel):
    asset: str
    claim: str
    status: Literal["proved", "ambiguous", "not_entailed", "unverified"]
    core: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    note: str = ""


class QualitativeAssetView(BaseModel):
    asset: str
    sign: Literal["+", "-", "0", "?"]
    direction: str
    definite: bool
    paths: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    explanation: str = ""


class SymbolicReport(BaseModel):
    node_count: int
    edge_count: int
    acyclic: bool
    cycles: list[list[str]] = Field(default_factory=list)
    qualitative: list[QualitativeAssetView] = Field(default_factory=list)
    proofs: list[ProofReport] = Field(default_factory=list)
    policy_results: list[PolicyResult] = Field(default_factory=list)
    ontology_issues: list[str] = Field(default_factory=list)
    proof_coverage: float = 0.0
    ledger_hash: str | None = None


class AnalysisResponse(BaseModel):
    event: MacroEvent
    graph: GraphPayload
    channel_activations: list[ChannelActivation]
    predictions: list[AssetPrediction]
    memo: Memo
    audit: AuditReport
    symbolic: SymbolicReport | None = None
    provenance: Provenance
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class LabeledEvent(MacroEvent):
    """An event with hand-curated labels used only for extraction evaluation."""

    gold_event_type: EventType
    gold_direction: Direction
    gold_magnitude: Magnitude | None = None
    gold_surprise: Surprise | None = None
    session: Literal["before_open", "during", "after_close", "non_trading"] = "during"
    tags: list[str] = Field(default_factory=list)


class DataSourceInfo(BaseModel):
    id: str
    name: str
    provider: str
    access: str
    frequency: str
    latency: str
    revision: str
    point_in_time: str
    license: str
    url: str
    notes: str = ""


class BacktestConfig(BaseModel):
    assets: list[str] | None = None
    dataset: Literal["curated", "fomc", "extended"] = "curated"
    window_start: int = 0
    window_end: int = 1  # primary window: the first session that prices the news
    estimation_start: int = -120
    estimation_end: int = -21
    flat_threshold_bps: float = 10.0
    train_fraction: float = 0.5
    bootstrap_samples: int = 500
    include_events: list[str] | None = None


class ModelMetrics(BaseModel):
    model: str
    n: int
    coverage: float
    accuracy: float | None = None
    brier: float | None = None
    log_loss: float | None = None
    auc: float | None = None
    ece: float | None = None
    accuracy_ci: tuple[float, float] | None = None
    brier_ci: tuple[float, float] | None = None


class AssetMetrics(BaseModel):
    asset: str
    n: int
    accuracy: float | None
    brier: float | None
    mean_car_bps: float | None


class EventTypeMetrics(BaseModel):
    event_type: str
    n_events: int
    n_predictions: int
    accuracy: float | None
    brier: float | None


class ModelComparison(BaseModel):
    model: str
    baseline: str
    delta_brier: float
    ci: tuple[float, float] | None = None
    p_value: float | None = None
    n_pairs: int


class CalibrationBin(BaseModel):
    bin_lower: float
    bin_upper: float
    n: int
    mean_predicted: float
    observed_frequency: float


class ExtractionMetrics(BaseModel):
    n: int
    event_type_accuracy: float
    direction_accuracy: float
    joint_accuracy: float
    confusion: dict[str, dict[str, int]] = Field(default_factory=dict)


class BacktestEventResult(BaseModel):
    event_id: str
    date: date
    headline: str
    event_type: str
    direction: str
    session: str
    predictions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    realized: dict[str, dict[str, Any]] = Field(default_factory=dict)
    extraction_correct: dict[str, bool] = Field(default_factory=dict)


class BacktestResponse(BaseModel):
    config: BacktestConfig
    n_events: int
    n_outcome_observations: int
    metrics: list[ModelMetrics]
    by_asset: list[AssetMetrics]
    by_event_type: list[EventTypeMetrics]
    calibration: list[CalibrationBin]
    comparisons: list[ModelComparison] = Field(default_factory=list)
    extraction: ExtractionMetrics
    events: list[BacktestEventResult]
    provenance: Provenance
    notes: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    headline: str = Field(min_length=3, max_length=2000)
    summary: str = Field(default="", max_length=8000)
    published_at: datetime | None = None
    source_name: str = "user"
    source_url: str | None = None
    source_tier: SourceTier = SourceTier.MEDIA
    model_config = ConfigDict(extra="forbid")


class BatchAnalyzeRequest(BaseModel):
    items: list[AnalyzeRequest] = Field(min_length=1, max_length=50)
