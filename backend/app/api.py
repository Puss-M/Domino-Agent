"""FastAPI surface.

The API is intentionally thin: it exposes the same engine the CLI uses and
returns the full evidence graph, not a chat completion. Expensive backtests
are cached by their config hash.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings, get_settings
from .datasources import DATA_SOURCES, MarketData
from .datasources.base import DataSourceError
from .evaluation.backtest import BacktestEngine
from .evaluation.dataset import DatasetError, load_events
from .evaluation.cross_sectional import evaluate_cross_sectional
from .evaluation.event_study import cross_sectional_test, event_study_summary
from .evaluation.temporal import audit_point_in_time
from .knowledge.loader import KnowledgeError
from .product import (
    ProductStore,
    build_digest,
    calendar_window,
    find_calendar_event,
    render_note_html,
    render_note_pdf,
    review_note,
)
from .product.calendar import calendar_payload
from .reasoning.engine import AnalysisEngine
from .symbolic import to_turtle
from .schemas import (
    AnalysisResponse,
    AnalyzeRequest,
    BacktestConfig,
    BacktestResponse,
    BatchAnalyzeRequest,
    CalendarCustomRequest,
    DataSourceInfo,
    LabeledEvent,
    NoteCreateRequest,
    NoteUpdateRequest,
    WatchlistRequest,
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
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    engine = AnalysisEngine(settings=settings)
    market = MarketData(settings)
    product_store = ProductStore(settings)
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
    def events(dataset: Literal["curated", "fomc", "fomc_surprise", "extended"] = "curated") -> list[dict]:
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
    def event_study(
        window_end: int = 1,
        dataset: Literal["curated", "fomc", "fomc_surprise", "extended"] = "curated",
    ) -> dict:
        events = load_events(settings=settings, dataset=dataset)
        config = BacktestConfig(window_end=window_end, dataset=dataset)
        prices = market.prices_wide(
            "adj_close", engine.transmission.assets + ["SPY"]
        ).dropna(how="all")
        from .evaluation.event_study import compute_outcomes

        outcomes, skipped = compute_outcomes(events, prices, engine.transmission.assets, config)
        return {
            "window_end": window_end,
            "dataset": dataset,
            "n_events": len(outcomes),
            "skipped": skipped,
            "summary": [
                event_study_summary(outcomes, asset) for asset in engine.transmission.assets
            ],
            "cross_sectional": cross_sectional_test(
                outcomes, events, prices, engine.transmission.assets, config
            ),
        }

    @app.get("/api/cross-sectional")
    def cross_sectional(
        dataset: Literal["curated", "fomc", "fomc_surprise", "extended"] = "curated",
    ) -> dict:
        events = load_events(settings=settings, dataset=dataset)
        prices = market.prices_wide(
            "adj_close", engine.transmission.assets + ["SPY"]
        ).dropna(how="all")
        return evaluate_cross_sectional(
            events,
            prices,
            engine.transmission.assets,
            BacktestConfig(dataset=dataset),
        )

    @app.get("/api/point-in-time")
    def point_in_time(
        dataset: Literal["curated", "fomc", "fomc_surprise", "extended"] = "curated",
    ) -> dict:
        events = load_events(settings=settings, dataset=dataset)
        prices = market.prices_wide("adj_close", ["SPY"]).dropna(how="all")
        price_last = prices.index[-1].date() if len(prices.index) else None
        return audit_point_in_time(
            events, dataset=dataset, price_last_date=price_last, settings=settings
        )

    # ------------------------------------------------------------ audit desk
    @app.get("/api/calendar")
    def calendar(days: int = 60, include_past: int = 0) -> dict:
        return calendar_window(
            days=max(1, min(days, 400)),
            include_past=max(0, min(include_past, 30)),
            settings=settings,
            store=product_store,
        )

    @app.post("/api/calendar/custom")
    def calendar_custom(request: CalendarCustomRequest) -> dict:
        return product_store.add_custom_calendar(request.model_dump())

    @app.get("/api/watchlist")
    def watchlist() -> dict:
        return {"assets": product_store.list_watchlist()}

    @app.post("/api/watchlist")
    def add_watchlist(request: WatchlistRequest) -> dict:
        try:
            assets = product_store.add_watchlist(request.asset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"assets": assets}

    @app.delete("/api/watchlist/{asset}")
    def remove_watchlist(asset: str) -> dict:
        return {"assets": product_store.remove_watchlist(asset)}

    @app.get("/api/audit-desk")
    def audit_desk() -> dict:
        calendar_payload_data = calendar_window(
            days=120, include_past=0, settings=settings, store=product_store
        )
        notes = product_store.list_notes(limit=200)
        return {
            "next_event": (
                calendar_payload_data["events"][0]
                if calendar_payload_data["events"]
                else None
            ),
            "n_upcoming": calendar_payload_data["n_events"],
            "watchlist": product_store.list_watchlist(),
            "n_notes": len(notes),
            "n_drafts": sum(1 for note in notes if note["status"] == "draft"),
            "n_reviewed": sum(1 for note in notes if note["status"] == "reviewed"),
        }

    @app.post("/api/notes")
    def create_note(request: NoteCreateRequest) -> dict:
        event_id = request.event_id
        headline = request.headline
        summary = request.summary
        session = request.session
        published = request.published_at
        source_name = request.source_name
        source_url = request.source_url
        if event_id:
            try:
                item = find_calendar_event(
                    event_id, settings=settings, store=product_store
                )
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="calendar event not found") from exc
            mapped = calendar_payload(item)
            headline = request.headline or mapped["headline"]
            summary = request.summary or mapped["summary"]
            session = request.session or mapped["session"]
            published = request.published_at or datetime.fromisoformat(
                mapped["published_at"]
            ).replace(tzinfo=timezone.utc)
            source_name = (
                request.source_name
                if request.source_name != "calendar"
                else mapped["source_name"]
            )
            source_url = request.source_url or mapped["source_url"]
        if not headline:
            raise HTTPException(status_code=400, detail="headline or event_id required")
        response = engine.analyze_headline(
            headline,
            summary=summary,
            published_at=published,
            source_name=source_name,
            source_url=source_url,
        )
        return product_store.create_note(
            response.model_dump(mode="json"), event_id=event_id, session=session
        )

    @app.get("/api/notes")
    def notes(
        query: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict:
        return {"notes": product_store.list_notes(query=query, status=status, limit=limit)}

    @app.get("/api/notes/{note_id}")
    def note(note_id: str) -> dict:
        try:
            return product_store.get_note(note_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="note not found") from exc

    @app.patch("/api/notes/{note_id}")
    def update_note(note_id: str, request: NoteUpdateRequest) -> dict:
        try:
            return product_store.update_note(
                note_id, status=request.status, review_notes=request.review_notes
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="note not found") from exc

    @app.post("/api/notes/{note_id}/review")
    def review(note_id: str) -> dict:
        try:
            saved = product_store.get_note(note_id)
            return review_note(saved, settings=settings, store=product_store)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="note not found") from exc

    @app.get("/api/notes/{note_id}/html", response_class=HTMLResponse)
    def note_html(note_id: str) -> HTMLResponse:
        try:
            saved = product_store.get_note(note_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="note not found") from exc
        return HTMLResponse(render_note_html(saved))

    @app.get("/api/notes/{note_id}/pdf")
    def note_pdf(note_id: str) -> Response:
        try:
            saved = product_store.get_note(note_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="note not found") from exc
        return Response(
            content=render_note_pdf(saved),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="domino-{note_id}.pdf"'
            },
        )

    @app.get("/api/digest")
    def digest(days: int = 14, format: Literal["html", "md"] = "html") -> Response:
        content = build_digest(
            product_store, settings=settings, days=max(1, min(days, 90)), fmt=format
        )
        if format == "md":
            return PlainTextResponse(content)
        return HTMLResponse(content)

    @app.get("/product", response_class=HTMLResponse)
    def product_page() -> HTMLResponse:
        path = Path(settings.frontend_dir) / "product.html"
        if not path.exists():
            raise HTTPException(status_code=404, detail="product page not found")
        return HTMLResponse(path.read_text(encoding="utf-8"))

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
