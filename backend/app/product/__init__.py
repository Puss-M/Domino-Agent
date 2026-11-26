"""Product layer: calendar, watchlist, saved notes, digest and review."""

from .calendar import calendar_window, load_calendar, find_calendar_event
from .digest import build_digest
from .note import render_note_html, render_note_pdf, review_note
from .store import ProductStore

__all__ = [
    "ProductStore",
    "build_digest",
    "calendar_window",
    "find_calendar_event",
    "load_calendar",
    "render_note_html",
    "render_note_pdf",
    "review_note",
]
