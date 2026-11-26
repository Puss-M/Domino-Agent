"""Daily/weekly digest for the Audit Desk.

The digest is deliberately plain: upcoming calendar events, the watchlist, and
recent saved notes with their review status. It is designed to be pasted into an
email or Slack message, not to be another dashboard.
"""

from __future__ import annotations

import html
from datetime import date

from .calendar import calendar_window


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def build_digest(store, settings=None, days: int = 14, fmt: str = "html") -> str:
    today = date.today()
    calendar = calendar_window(days=days, include_past=0, settings=settings, store=store)
    upcoming = [event for event in calendar["events"] if not event.get("is_past")]
    notes = store.list_notes(limit=12)
    watchlist = store.list_watchlist()

    lines = [
        f"# Macro Audit Digest — {today.isoformat()}",
        "",
        f"Watchlist: {', '.join(watchlist) if watchlist else 'none'}",
        "",
        "## Upcoming events",
    ]
    if upcoming:
        for event in upcoming:
            lines.append(
                f"- {event['date']} {event.get('time', '')} — {event['title']} "
                f"({event.get('importance', 'medium')}, {event.get('source', '')})"
            )
    else:
        lines.append("- No events in the window.")
    lines.extend(["", "## Recent notes"])
    if notes:
        for note in notes:
            review = note.get("review") or {}
            review_text = (
                f"reviewed: hit rate {review.get('hit_rate')}"
                if review
                else "not reviewed"
            )
            lines.append(
                f"- {note['created_at'][:10]} — {note['headline']} "
                f"[{note['status']}; {review_text}; "
                f"{note.get('n_proved', 0)} proved / {note.get('n_ambiguous', 0)} ambiguous]"
            )
    else:
        lines.append("- No saved notes yet.")
    lines.extend(
        [
            "",
            "## Next action",
            "- Open the Audit Desk, review the next event, save a note, and export the PDF.",
            "",
            "_Research prototype. Not investment advice._",
        ]
    )
    markdown = "\n".join(lines)
    if fmt != "html":
        return markdown

    event_rows = "".join(
        f"<tr><td>{_esc(event['date'])}<br><span class='muted'>{_esc(event.get('time', ''))}</span></td>"
        f"<td>{_esc(event['title'])}<br><span class='muted'>{_esc(event.get('source', ''))}</span></td>"
        f"<td>{_esc(event.get('importance', 'medium'))}</td></tr>"
        for event in upcoming
    ) or "<tr><td colspan='3'>No events in the window.</td></tr>"
    note_rows = "".join(
        f"<tr><td>{_esc(note['created_at'][:10])}</td>"
        f"<td>{_esc(note['headline'])}</td>"
        f"<td>{_esc(note['status'])}</td>"
        f"<td>{_esc((note.get('review') or {}).get('hit_rate', '-'))}</td></tr>"
        for note in notes
    ) or "<tr><td colspan='4'>No saved notes yet.</td></tr>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Macro Audit Digest — {today.isoformat()}</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; background: #f5f0e6;
  color: #211b16; margin: 0; padding: 28px; }}
main {{ max-width: 860px; margin: 0 auto; background: #fffdf8;
  border: 1px solid #d9cdbb; padding: 26px 30px; }}
.kicker {{ font-family: Arial, sans-serif; font-size: 10px; letter-spacing: .12em;
  text-transform: uppercase; color: #a51c30; }}
h1 {{ font-size: 26px; margin: 4px 0 2px; }}
.muted {{ color: #7b6f61; font-family: Arial, sans-serif; font-size: 11px; }}
table {{ width: 100%; border-collapse: collapse; font-family: Arial, sans-serif;
  font-size: 12px; margin: 8px 0 18px; }}
th, td {{ text-align: left; border-bottom: 1px solid #e4dacb; padding: 6px 4px; }}
th {{ font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: #7b6f61; }}
footer {{ margin-top: 18px; border-top: 1px solid #d9cdbb; padding-top: 8px;
  font-family: Arial, sans-serif; font-size: 10px; color: #7b6f61; }}
</style></head><body><main>
<div class="kicker">Domino · Macro Audit Digest</div>
<h1>{today.isoformat()}</h1>
<p class="muted">Watchlist: {_esc(', '.join(watchlist) if watchlist else 'none')}</p>
<h2>Upcoming events</h2>
<table><thead><tr><th>When</th><th>Event</th><th>Importance</th></tr></thead>
<tbody>{event_rows}</tbody></table>
<h2>Recent notes</h2>
<table><thead><tr><th>Date</th><th>Headline</th><th>Status</th><th>Hit rate</th></tr></thead>
<tbody>{note_rows}</tbody></table>
<p>Open the Audit Desk, review the next event, save a note, and export the PDF.</p>
<footer>Research prototype. Not investment advice. Proofs are relative to the cited mechanism library.</footer>
</main></body></html>"""
