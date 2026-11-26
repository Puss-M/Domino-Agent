"""One-page event note rendering, PDF export and post-event review."""

from __future__ import annotations

import html
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import Settings, get_settings
from ..datasources import MarketData
from ..evaluation.event_study import compute_outcomes
from ..schemas import (
    BacktestConfig,
    Direction,
    EventType,
    LabeledEvent,
    Magnitude,
    SourceRef,
    Surprise,
)

_FONT_NAME: str | None = None


def _font_name() -> str:
    global _FONT_NAME
    if _FONT_NAME:
        return _FONT_NAME
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("NoteFont", str(path)))
            _FONT_NAME = "NoteFont"
            return _FONT_NAME
        except Exception:
            continue
    _FONT_NAME = "Helvetica"
    return _FONT_NAME


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def _pct(value: object) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "-"


def _proof_map(payload: dict) -> dict[str, dict]:
    symbolic = payload.get("symbolic") or {}
    return {proof.get("asset"): proof for proof in symbolic.get("proofs", [])}


def render_note_html(note: dict) -> str:
    payload = note.get("payload") or {}
    event = payload.get("event") or {}
    memo = payload.get("memo") or {}
    symbolic = payload.get("symbolic") or {}
    review = note.get("review") or {}
    proofs = _proof_map(payload)
    magnitude = event.get("magnitude") or {}
    surprise = event.get("surprise") or {}

    asset_rows = []
    for prediction in payload.get("predictions", []):
        proof = proofs.get(prediction.get("asset"), {})
        asset_rows.append(
            "<tr>"
            f"<td>{_esc(prediction.get('asset'))}</td>"
            f"<td>{_esc(prediction.get('direction'))}</td>"
            f"<td class='num'>{_pct(prediction.get('p_up'))}</td>"
            f"<td class='num'>{float(prediction.get('expected_car_bps', 0)):+.0f}bp</td>"
            f"<td>{_esc(proof.get('status', 'unverified'))}</td>"
            "</tr>"
        )
    policies = symbolic.get("policy_results") or []
    failed = [policy for policy in policies if not policy.get("passed")]
    policy_html = "".join(
        f"<li class='{'fail' if not policy.get('passed') else 'pass'}'>"
        f"{_esc(policy.get('id'))} {_esc(policy.get('title'))}: "
        f"{_esc(policy.get('detail'))}</li>"
        for policy in policies
    )
    review_html = ""
    if review:
        misses = review.get("misses") or []
        review_html = f"""
        <section>
          <h2>Post-event review</h2>
          <p><strong>{_esc(review.get('status', 'reviewed'))}</strong> ·
          hit rate {_pct(review.get('hit_rate'))} · n={_esc(review.get('n', 0))} ·
          earliest stage: {_esc(review.get('attribution', 'n/a'))}</p>
          {f"<p>{_esc(review.get('review_notes'))}</p>" if review.get('review_notes') else ""}
          <ul>{''.join(f"<li>{_esc(m)}</li>" for m in misses)}</ul>
        </section>
        """
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{_esc(note.get('headline'))} · Domino Audit Note</title>
<style>
@page {{ size: A4; margin: 16mm; }}
body {{ font-family: Georgia, "Times New Roman", serif; color: #211b16;
  background: #fffdf8; margin: 0; padding: 2mm; font-size: 11px; line-height: 1.45; }}
header {{ border-bottom: 2px solid #211b16; padding-bottom: 8px; margin-bottom: 12px; }}
.kicker {{ font-family: Arial, sans-serif; font-size: 9px; letter-spacing: .12em;
  text-transform: uppercase; color: #a51c30; }}
h1 {{ font-size: 22px; margin: 4px 0 2px; line-height: 1.15; }}
h2 {{ font-family: Arial, sans-serif; font-size: 11px; letter-spacing: .08em;
  text-transform: uppercase; border-bottom: 1px solid #d9cdbb; padding-bottom: 2px; margin: 14px 0 6px; }}
.meta {{ font-family: Arial, sans-serif; font-size: 9px; color: #4a4037; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 18px; }}
table {{ width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 9px; }}
th, td {{ border-bottom: 1px solid #e4dacb; padding: 3px 4px; text-align: left; }}
th {{ font-size: 8px; letter-spacing: .06em; text-transform: uppercase; color: #7b6f61; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
ul {{ margin: 4px 0 0 16px; padding: 0; }}
li {{ margin: 2px 0; }}
.pass {{ color: #0d6b5c; }}
.fail {{ color: #a51c30; }}
.hash {{ font-family: Consolas, monospace; font-size: 8px; color: #7b6f61;
  word-break: break-all; margin-top: 4px; }}
footer {{ margin-top: 16px; border-top: 1px solid #d9cdbb; padding-top: 6px;
  font-family: Arial, sans-serif; font-size: 8px; color: #7b6f61; }}
@media print {{ body {{ background: #fff; }} }}
</style></head>
<body>
<header>
  <div class="kicker">Domino · Macro Event Audit</div>
  <h1>{_esc(event.get('headline') or note.get('headline'))}</h1>
  <div class="meta">Event type {_esc(event.get('event_type'))} · direction
    {_esc(event.get('direction'))} · published {_esc(event.get('published_at'))} ·
    confidence {_pct(event.get('confidence'))} · note {_esc(note.get('id'))}</div>
</header>

<section class="grid">
  <div><h2>Event</h2>
    <p>Magnitude: <strong>{_esc(magnitude.get('value', '-'))} {_esc(magnitude.get('unit', ''))}</strong><br>
    Surprise: <strong>{_esc(surprise.get('value', 'not quantified'))} {_esc(surprise.get('unit', ''))}</strong>
    ({_esc(surprise.get('sign', 'neutral'))})</p>
    <p>{_esc(memo.get('summary'))}</p>
  </div>
  <div><h2>Symbolic verification</h2>
    <p>{_esc(symbolic.get('node_count', 0))} nodes · {_esc(symbolic.get('edge_count', 0))} edges ·
    {('acyclic' if symbolic.get('acyclic') else 'cycle')} ·
    proof coverage {_pct(symbolic.get('proof_coverage'))}</p>
    <p>{_esc(sum(1 for p in proofs.values() if p.get('status') == 'proved'))} proved ·
    {_esc(sum(1 for p in proofs.values() if p.get('status') == 'ambiguous'))} ambiguous</p>
    <div class="hash">ledger {_esc(symbolic.get('ledger_hash') or note.get('ledger_hash'))}</div>
  </div>
</section>

<h2>Asset views</h2>
<table><thead><tr><th>Asset</th><th>Direction</th><th class="num">P(up)</th>
<th class="num">5d prior</th><th>Proof</th></tr></thead>
<tbody>{''.join(asset_rows)}</tbody></table>

<section class="grid">
  <div><h2>Transmission</h2>
    <ul>{''.join(f"<li>{_esc(item)}</li>" for item in memo.get('transmission', []))}</ul>
  </div>
  <div><h2>What would falsify this</h2>
    <ul>{''.join(f"<li>{_esc(item)}</li>" for item in memo.get('falsifiers', []))}</ul>
  </div>
</section>

<section>
  <h2>Policies</h2>
  <ul>{policy_html}</ul>
  {f"<p class='fail'>{len(failed)} policy issue(s)</p>" if failed else "<p class='pass'>All policies passed.</p>"}
</section>

{review_html}

<footer>
  Research prototype. This is a transmission hypothesis, not investment advice or
  an identified causal effect. Proofs are relative to the cited mechanism library.
  Data and code: https://github.com/Puss-M/Domino-Agent
</footer>
</body></html>"""


def render_note_pdf(note: dict) -> bytes:
    payload = note.get("payload") or {}
    event = payload.get("event") or {}
    memo = payload.get("memo") or {}
    symbolic = payload.get("symbolic") or {}
    review = note.get("review") or {}
    proofs = _proof_map(payload)
    font = _font_name()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "NoteTitle", parent=styles["Title"], fontName=font, fontSize=18, leading=21,
        alignment=0, spaceAfter=4,
    )
    small = ParagraphStyle(
        "NoteSmall", parent=styles["BodyText"], fontName=font, fontSize=8, leading=10,
        textColor=colors.HexColor("#4a4037"),
    )
    body = ParagraphStyle(
        "NoteBody", parent=styles["BodyText"], fontName=font, fontSize=9, leading=12,
    )
    heading = ParagraphStyle(
        "NoteHeading", parent=styles["Heading2"], fontName=font, fontSize=10, leading=12,
        textColor=colors.HexColor("#211b16"), spaceBefore=8, spaceAfter=3,
    )
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=note.get("headline", "Domino audit note"),
        author="Domino-Agent Team",
        subject="Macro event audit note",
    )
    story = [
        Paragraph("DOMINO | MACRO EVENT AUDIT", ParagraphStyle(
            "Kicker", parent=small, textColor=colors.HexColor("#a51c30"), fontSize=7,
            leading=9,
        )),
        Paragraph(_esc(event.get("headline") or note.get("headline")), title),
        Paragraph(
            f"Event type {_esc(event.get('event_type'))} | direction "
            f"{_esc(event.get('direction'))} | published {_esc(event.get('published_at'))} "
            f"| confidence {_pct(event.get('confidence'))} | note {_esc(note.get('id'))}",
            small,
        ),
        Spacer(1, 6),
        Paragraph("Event", heading),
        Paragraph(_esc(memo.get("summary")), body),
        Paragraph("Symbolic verification", heading),
        Paragraph(
            f"{_esc(symbolic.get('node_count', 0))} nodes | "
            f"{_esc(symbolic.get('edge_count', 0))} edges | "
            f"{'acyclic' if symbolic.get('acyclic') else 'cycle'} | proof coverage "
            f"{_pct(symbolic.get('proof_coverage'))}. Ledger: "
            f"{_esc(symbolic.get('ledger_hash') or note.get('ledger_hash'))}",
            small,
        ),
        Paragraph("Asset views", heading),
    ]
    rows = [[
        Paragraph("Asset", small), Paragraph("Direction", small),
        Paragraph("P(up)", small), Paragraph("5d prior", small), Paragraph("Proof", small),
    ]]
    for prediction in payload.get("predictions", []):
        proof = proofs.get(prediction.get("asset"), {})
        rows.append([
            Paragraph(_esc(prediction.get("asset")), body),
            Paragraph(_esc(prediction.get("direction")), body),
            Paragraph(_pct(prediction.get("p_up")), body),
            Paragraph(f"{float(prediction.get('expected_car_bps', 0)):+.0f}bp", body),
            Paragraph(_esc(proof.get("status", "unverified")), body),
        ])
    table = Table(rows, colWidths=[32 * mm, 28 * mm, 22 * mm, 28 * mm, 40 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#7b6f61")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#d9cdbb")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e4dacb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(table)
    story.append(Paragraph("Transmission", heading))
    story.extend(Paragraph(_esc(item), body) for item in memo.get("transmission", []))
    story.append(Paragraph("What would falsify this", heading))
    story.extend(Paragraph("• " + _esc(item), body) for item in memo.get("falsifiers", []))
    story.append(Paragraph("Policies", heading))
    for policy in symbolic.get("policy_results", []):
        color = "#0d6b5c" if policy.get("passed") else "#a51c30"
        story.append(Paragraph(
            f"<font color='{color}'>{_esc(policy.get('id'))}</font> "
            f"{_esc(policy.get('title'))}: {_esc(policy.get('detail'))}", small,
        ))
    if review:
        story.append(Paragraph("Post-event review", heading))
        story.append(Paragraph(
            f"{_esc(review.get('status', 'reviewed'))} | hit rate "
            f"{_pct(review.get('hit_rate'))} | n={_esc(review.get('n', 0))} | "
            f"earliest stage: {_esc(review.get('attribution', 'n/a'))}", body,
        ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Research prototype. This is a transmission hypothesis, not investment "
        "advice or an identified causal effect. Proofs are relative to the cited "
        "mechanism library.", small,
    ))
    document.build(story)
    return buffer.getvalue()


def _build_labeled_event(payload: dict, session: str) -> LabeledEvent:
    event = payload.get("event") or {}
    magnitude = event.get("magnitude")
    surprise = event.get("surprise")
    return LabeledEvent(
        id=event.get("id") or "note-event",
        headline=event.get("headline", ""),
        summary=event.get("summary", ""),
        published_at=event.get("published_at"),
        source=SourceRef(name=(event.get("source") or {}).get("name", "note")),
        event_type=EventType(event.get("event_type", "other")),
        direction=Direction(event.get("direction", "neutral")),
        actor=event.get("actor"),
        magnitude=Magnitude(**magnitude) if magnitude else None,
        surprise=Surprise(**surprise) if surprise else None,
        keywords=event.get("keywords", []),
        entities=event.get("entities", []),
        confidence=float(event.get("confidence", 0.5)),
        extraction_method=event.get("extraction_method", "rules-v1"),
        text_sentiment=event.get("text_sentiment", {}),
        gold_event_type=EventType(event.get("event_type", "other")),
        gold_direction=Direction(event.get("direction", "neutral")),
        session=session or "during",
    )


def review_note(
    note: dict,
    settings: Settings | None = None,
    store=None,
) -> dict:
    settings = settings or get_settings()
    payload = note.get("payload") or {}
    event = _build_labeled_event(payload, note.get("session", "during"))
    assets = [
        prediction.get("asset")
        for prediction in payload.get("predictions", [])
        if prediction.get("asset")
    ]
    market = MarketData(settings)
    prices = market.prices_wide("adj_close", assets + ["SPY"]).dropna(how="all")
    outcomes, _ = compute_outcomes(
        [event], prices, assets, BacktestConfig(window_end=1)
    )
    event_outcomes = outcomes.get(event.id, {})
    if not event_outcomes:
        review = {
            "status": "pending",
            "reason": "outcome window is not available in the local price snapshot",
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    else:
        proofs = _proof_map(payload)
        hits = 0
        n = 0
        misses = []
        stages: dict[str, int] = {}
        for prediction in payload.get("predictions", []):
            asset = prediction.get("asset")
            outcome = event_outcomes.get(asset)
            if not outcome or outcome.direction == "flat":
                continue
            n += 1
            predicted = prediction.get("direction")
            if predicted == outcome.direction:
                hits += 1
                continue
            proof = proofs.get(asset, {})
            if float(event.confidence) < 0.6:
                stage = "perception"
            elif not prediction.get("mechanisms"):
                stage = "retrieval"
            elif proof.get("status") in {"ambiguous", "not_entailed"}:
                stage = "symbolic"
            else:
                stage = "transmission"
            stages[stage] = stages.get(stage, 0) + 1
            misses.append(
                f"{asset}: predicted {predicted}, realized {outcome.direction} "
                f"({outcome.car_bps:+.0f}bp, proof {proof.get('status', 'unverified')})"
            )
        priority = ["perception", "retrieval", "symbolic", "transmission"]
        attribution = next((stage for stage in priority if stages.get(stage)), "none")
        review = {
            "status": "reviewed",
            "hit_rate": round(hits / n, 4) if n else None,
            "n": n,
            "hits": hits,
            "attribution": attribution,
            "stage_counts": stages,
            "misses": misses[:12],
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "window": {
                "start": min(o.window_start for o in event_outcomes.values()).isoformat(),
                "end": max(o.window_end for o in event_outcomes.values()).isoformat(),
            },
        }
    if store is not None:
        return store.set_review(note["id"], review)
    return {**note, "review": review}
