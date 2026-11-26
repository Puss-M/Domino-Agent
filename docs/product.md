# Audit Desk — product line

The Audit Desk is the product surface for Domino: a recurring workflow for a
macro analyst, not a chat box.

> Calendar → scenario note → one-page audit → PDF/share → digest → post-event review.

The research cockpit at `/` remains the deep-inspection surface. The Audit Desk
at `/product` is where the work happens every week.

## The job

A macro analyst has a calendar. Before an event they need a defensible prior:
what channels are in play, which assets are directionally clear, which are
ambiguous, and what would falsify the view. After the event they need to know
whether the note was right, and if not, where the chain broke first.

Domino produces that note deterministically: a rule-first event extraction, a
cited mechanism graph, sign algebra, an SMT proof core, a policy result, and a
hash-chained ledger record. The desk adds the product workflow around it.

## What is implemented

| Surface | What it does |
|---|---|
| **Calendar** | Sourced upcoming FOMC and BEA events; custom events can be added. |
| **Scenario note** | For FOMC, choose Hike 25bp / Cut 25bp / Hawkish hold / Dovish hold / No scenario. A scenario is explicitly not a forecast. |
| **Saved notes** | SQLite persistence; list/search/filter; status draft/reviewed/archived. |
| **One-page note** | Event, asset views, proof badges, transmission, falsifiers, policies, ledger hash, review. |
| **PDF** | Server-side ReportLab export, two pages, A4, with metadata. |
| **Share link** | `/api/notes/{id}/html` is a self-contained, print-ready note. |
| **Watchlist** | Persistent asset list used by the digest. |
| **Digest** | HTML and Markdown digest of upcoming events, watchlist and recent notes. |
| **Post-event review** | Computes realised CAR[0,+1], hit rate and the earliest responsible stage (perception / retrieval / symbolic / transmission). |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/calendar?days=60` | Upcoming calendar events |
| POST | `/api/calendar/custom` | Add a custom event |
| GET | `/api/audit-desk` | Header counts and next event |
| GET/POST | `/api/watchlist` | List/add watchlist assets |
| DELETE | `/api/watchlist/{asset}` | Remove an asset |
| POST | `/api/notes` | Analyze and save a note (headline or calendar event) |
| GET | `/api/notes` | List/search saved notes |
| GET | `/api/notes/{id}` | Full saved analysis |
| PATCH | `/api/notes/{id}` | Update status or review notes |
| POST | `/api/notes/{id}/review` | Compute realised outcomes and attribution |
| GET | `/api/notes/{id}/html` | Print-ready one-page note |
| GET | `/api/notes/{id}/pdf` | PDF export |
| GET | `/api/digest?format=html\|md` | Digest |

## Data and provenance

- Calendar: Federal Reserve FOMC calendar and BEA release schedule, with source
  URLs stored on each event. This is a curated seed, not a complete economic
  calendar.
- Notes: the full `AnalysisResponse` is stored as JSON, including the event,
  predictions, proof statuses, policy results and ledger hash.
- Review: uses the local Yahoo adjusted-close snapshot and the same market-model
  event study as the research cockpit. The point-in-time caveat in
  [`point_in_time.md`](point_in_time.md) applies to the review too.
- Database: `backend/.cache/product.db` (SQLite, WAL). It is local and ignored by
  git; the schema is small enough to port to Postgres.

## Run

```bash
uvicorn backend.main:app --reload
# research cockpit: http://127.0.0.1:8000/
# audit desk:       http://127.0.0.1:8000/product
```

The product layer is offline and single-user. It has no authentication, no
scheduled email delivery, no multi-tenant isolation and no live PIT feed. Those
are deployment work, not hidden features.

## Product metrics to track with design partners

1. **Time to note**: minutes from event selection to a saved, exported note.
2. **Review rate**: saved notes that get a post-event review within 48 hours.
3. **Correction rate**: notes where the review changes the analyst's view.
4. **Ambiguity acceptance**: how often the analyst keeps an `ambiguous` asset
   instead of forcing a direction.
5. **Weekly active analysts** and notes per analyst per week.

## Roadmap

- P0: point-in-time prices and consensus/surprise; scheduled digest delivery
  (email/Slack); auth + Postgres.
- P1: period/entity/scope provenance (E12); FAAB-style trace attribution;
  more calendar sources.
- P2: team workspaces, approval flow, retention/WORM, independent model
  validation.
