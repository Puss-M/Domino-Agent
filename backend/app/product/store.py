"""SQLite persistence for the Audit Desk.

The product layer deliberately uses SQLite: the offline demo must run with one
command and no external service. The schema is small enough to port to Postgres
without changing the API contract.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings, get_settings

DEFAULT_WATCHLIST = ["SPY", "QQQ", "TLT", "GLD", "UUP"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProductStore:
    def __init__(self, settings: Settings | None = None, path: Path | None = None):
        settings = settings or get_settings()
        self.path = path or (settings.cache_dir / "product.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS watchlist (
                        asset TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS notes (
                        id TEXT PRIMARY KEY,
                        event_id TEXT,
                        headline TEXT NOT NULL,
                        event_type TEXT,
                        direction TEXT,
                        session TEXT NOT NULL DEFAULT 'during',
                        status TEXT NOT NULL DEFAULT 'draft',
                        payload TEXT NOT NULL,
                        review TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS notes_created_idx ON notes(created_at);
                    CREATE TABLE IF NOT EXISTS custom_calendar (
                        id TEXT PRIMARY KEY,
                        date TEXT NOT NULL,
                        time TEXT,
                        event_type TEXT,
                        title TEXT NOT NULL,
                        summary TEXT,
                        importance TEXT,
                        session TEXT,
                        source TEXT,
                        url TEXT,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                count = connection.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
                if count == 0:
                    for asset in DEFAULT_WATCHLIST:
                        connection.execute(
                            "INSERT OR IGNORE INTO watchlist(asset, created_at) VALUES (?, ?)",
                            (asset, _now()),
                        )

    # ------------------------------------------------------------- watchlist
    def list_watchlist(self) -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT asset FROM watchlist ORDER BY asset"
            ).fetchall()
        return [row["asset"] for row in rows]

    def add_watchlist(self, asset: str) -> list[str]:
        symbol = asset.strip().upper()
        if not symbol or len(symbol) > 8:
            raise ValueError("asset must be 1-8 characters")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO watchlist(asset, created_at) VALUES (?, ?)",
                    (symbol, _now()),
                )
        return self.list_watchlist()

    def remove_watchlist(self, asset: str) -> list[str]:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "DELETE FROM watchlist WHERE asset = ?", (asset.strip().upper(),)
                )
        return self.list_watchlist()

    # ----------------------------------------------------------------- notes
    def create_note(self, payload: dict, event_id: str | None, session: str) -> dict:
        note_id = uuid.uuid4().hex
        event = payload.get("event", {})
        now = _now()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO notes(id, event_id, headline, event_type, direction,
                                      session, status, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)
                    """,
                    (
                        note_id,
                        event_id,
                        event.get("headline", ""),
                        event.get("event_type"),
                        event.get("direction"),
                        session,
                        json.dumps(payload, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
        return self.get_note(note_id)

    def _note_row(self, row: sqlite3.Row, *, include_payload: bool = True) -> dict:
        payload = json.loads(row["payload"]) if row["payload"] else {}
        review = json.loads(row["review"]) if row["review"] else None
        predictions = payload.get("predictions", [])
        proofs = (payload.get("symbolic") or {}).get("proofs", [])
        note = {
            "id": row["id"],
            "event_id": row["event_id"],
            "headline": row["headline"],
            "event_type": row["event_type"],
            "direction": row["direction"],
            "session": row["session"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "review": review,
            "n_assets": len(predictions),
            "proof_coverage": (payload.get("symbolic") or {}).get("proof_coverage"),
            "ledger_hash": (payload.get("symbolic") or {}).get("ledger_hash"),
            "n_proved": sum(1 for proof in proofs if proof.get("status") == "proved"),
            "n_ambiguous": sum(1 for proof in proofs if proof.get("status") == "ambiguous"),
        }
        if include_payload:
            note["payload"] = payload
        return note

    def get_note(self, note_id: str) -> dict:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
        if row is None:
            raise KeyError(note_id)
        return self._note_row(row)

    def list_notes(
        self,
        query: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if query:
            clauses.append("(headline LIKE ? OR event_type LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(limit, 200)))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM notes {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._note_row(row, include_payload=False) for row in rows]

    def update_note(
        self,
        note_id: str,
        status: str | None = None,
        review_notes: str | None = None,
    ) -> dict:
        note = self.get_note(note_id)
        review = note.get("review") or {}
        if review_notes is not None:
            review["review_notes"] = review_notes
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "UPDATE notes SET status = ?, review = ?, updated_at = ? WHERE id = ?",
                    (
                        status or note["status"],
                        json.dumps(review, ensure_ascii=False) if review else None,
                        _now(),
                        note_id,
                    ),
                )
        return self.get_note(note_id)

    def set_review(self, note_id: str, review: dict) -> dict:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "UPDATE notes SET review = ?, status = 'reviewed', updated_at = ? WHERE id = ?",
                    (json.dumps(review, ensure_ascii=False), _now(), note_id),
                )
        return self.get_note(note_id)

    def delete_note(self, note_id: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    # ------------------------------------------------------------- calendar
    def add_custom_calendar(self, payload: dict) -> dict:
        entry_id = "custom-" + uuid.uuid4().hex[:12]
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO custom_calendar(id, date, time, event_type, title, summary,
                                                importance, session, source, url, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        payload["date"],
                        payload.get("time", ""),
                        payload.get("event_type", "other"),
                        payload["title"],
                        payload.get("summary", ""),
                        payload.get("importance", "medium"),
                        payload.get("session", "during"),
                        payload.get("source", "custom"),
                        payload.get("url", ""),
                        _now(),
                    ),
                )
        return self.get_custom_calendar(entry_id)

    def get_custom_calendar(self, entry_id: str) -> dict:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM custom_calendar WHERE id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            raise KeyError(entry_id)
        return dict(row)

    def list_custom_calendar(self) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM custom_calendar ORDER BY date"
            ).fetchall()
        return [dict(row) for row in rows]
