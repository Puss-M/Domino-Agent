"""FastAPI surface.

The API is intentionally thin: it exposes the same engine the CLI uses and
returns the full evidence graph, not a chat completion. Expensive backtests
are cached by their config hash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings, get_settings
from .datasources import DATA_SOURCES, MarketData
from .datasources.base import DataSourceError
from .evaluation.backtest import BacktestEngine
from .evaluation.dataset import DatasetError, load_events
from .evaluation.event_study import event_study_summary
from .knowledge.loader import KnowledgeError
from .reasoning.engine import AnalysisEngine
from .symbolic import to_turtle
from .schemas import (
    AnalysisResponse,
    AnalyzeRequest,
    BacktestConfig,
    BacktestResponse,
    BatchAnalyzeRequest,
    DataSourceInfo,
    LabeledEvent,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Domino Agent",
        version=__version__,
        description=(
            "Auditable event-driven macro transmission analysis: rule-first extraction, "
            "cited mechanism retrieval, deterministic channel/asset transmission, and "
            "event-study calibration."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    engine = AnalysisEngine(settings=settings)
    market = MarketData(settings)
    backtest_cache: dict[str, BacktestResponse] = {}

    def _event_payload(event: LabeledEvent) -> dict:
        return {
            "id": event.id,
            "date": event.published_at.date().isoformat(),
            "published_at": event.published_at.isoformat(),
            "headline": event.headline,
            "event_type": event.event_type.value,
            "direction": event.direction.value,
            "session": event.session,
            "tags": event.tags,
            "source": event.source.model_dump(mode="json"),
        }

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "knowledge_version": engine.knowledge.version,
            "n_mechanisms": len(engine.knowledge.mechanisms),
            "n_channels": len(engine.knowledge.channels),
            "n_events": len(load_events(settings=settings)),
            "data_sources": len(DATA_SOURCES),
            "offline": True,
        }

    @app.get("/api/data-sources", response_model=list[DataSourceInfo])
    def data_sources() -> list[DataSourceInfo]:
        return DATA_SOURCES

    @app.get("/api/ontology.ttl", response_class=PlainTextResponse)
    def ontology() -> str:
        return to_turtle(engine.knowledge)

    @app.get("/api/mechanisms")
    def mechanisms() -> list[dict]:
        return [
            {
                "id": mechanism.id,
                "title": mechanism.title,
                "event_types": [event_type.value for event_type in mechanism.event_types],
                "directions": [direction.value for direction in mechanism.directions],
                "actors": mechanism.actors,
                "confidence": mechanism.confidence,
                "evidence_grade": mechanism.evidence_grade.value,
                "horizon_days": mechanism.horizon_days,
                "channels": mechanism.channels,
                "citations": mechanism.citations,
            }
            for mechanism in engine.knowledge.mechanisms
        ]

    @app.get("/api/events")
    def events(dataset: Literal["curated", "fomc", "extended"] = "curated") -> list[dict]:
        return [
            _event_payload(event)
            for event in load_events(settings=settings, dataset=dataset)
        ]

    @app.post("/api/analyze", response_model=AnalysisResponse)
    def analyze(request: AnalyzeRequest) -> AnalysisResponse:
        try:
            return engine.analyze_headline(
                request.headline,
                summary=request.summary,
                published_at=request.published_at,
                source_name=request.source_name,
                source_url=request.source_url,
                source_tier=request.source_tier,
            )
        except DataSourceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except (KnowledgeError, DatasetError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/analyze/batch", response_model=list[AnalysisResponse])
    def analyze_batch(request: BatchAnalyzeRequest) -> list[AnalysisResponse]:
        try:
            return engine.analyze_batch(request)
        except DataSourceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/backtest", response_model=BacktestResponse)
    def backtest(config: BacktestConfig) -> BacktestResponse:
        key = config.model_dump_json()
        if key in backtest_cache:
            return backtest_cache[key]
        try:
            result = BacktestEngine(settings=settings, config=config).run(config)
        except (KnowledgeError, DatasetError, DataSourceError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        backtest_cache[key] = result
        return result

    @app.get("/api/backtest/latest", response_model=BacktestResponse)
    def backtest_latest() -> BacktestResponse:
        config = BacktestConfig()
        key = config.model_dump_json()
        if key not in backtest_cache:
            backtest_cache[key] = BacktestEngine(settings=settings, config=config).run(config)
        return backtest_cache[key]

    @app.get("/api/event-study")
    def event_study(window_end: int = 1) -> dict:
        events = load_events(settings=settings)
        config = BacktestConfig(window_end=window_end)
        prices = market.prices_wide("adj_close", engine.transmission.assets + ["SPY"]).dropna(how="all")
        from .evaluation.event_study import compute_outcomes

        outcomes, skipped = compute_outcomes(events, prices, engine.transmission.assets, config)
        return {
            "window_end": window_end,
            "n_events": len(outcomes),
            "skipped": skipped,
            "summary": [
                event_study_summary(outcomes, asset) for asset in engine.transmission.assets
            ],
        }

    @app.get("/api/market/{ticker}")
    def market_snapshot(ticker: str) -> dict:
        symbol = ticker.upper()
        if symbol not in engine.transmission.assets and symbol != "SPY":
            raise HTTPException(status_code=404, detail=f"unknown ticker {ticker}")
        prices = market.prices_wide("adj_close", [symbol])
        if prices.empty:
            raise HTTPException(status_code=404, detail=f"no data for {ticker}")
        series = prices[symbol].dropna()
        last_date = series.index[-1]
        return {
            "ticker": symbol,
            "date": last_date.date().isoformat(),
            "adj_close": round(float(series.iloc[-1]), 4),
            "source": "local snapshot (Yahoo Finance)",
        }

    @app.exception_handler(DataSourceError)
    def data_source_error(_request, exc: DataSourceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    frontend = Path(settings.frontend_dir)
    if frontend.exists() and (frontend / "index.html").exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    else:

        @app.get("/")
        def root() -> dict:
            return {
                "service": "Domino Agent",
                "docs": "/docs",
                "health": "/api/health",
                "note": "frontend build not found",
            }

    return app


app = create_app()
