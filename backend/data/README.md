# Bundled data

Everything in this directory is either curated by the project or a small, redistributable public-data snapshot. The app runs offline from these files.

| Path | What it is | Refresh |
|---|---|---|
| `events/events.yaml` | 50 dated, labelled macro events | edit by hand; see `CONTRIBUTING.md` |
| `knowledge/mechanisms.yaml` | 20 cited mechanisms, 14 channels, asset loadings | edit by hand; add a citation and a test |
| `market/prices.csv` | 12 ETFs, daily adjusted close, 2015–present | `python scripts/fetch_market_snapshot.py` |
| `market/provenance.json` | endpoint, retrieval time, row counts, caveats | written by the fetch script |
| `macro/treasury_yields_2024.csv` | daily Treasury curve | `python scripts/fetch_public_snapshots.py` |
| `sec/aapl_sample.json` | one 8-K exhibit (truncated) + XBRL revenue history | `python scripts/fetch_public_snapshots.py` |
| `news/gdelt_fed_sample.json` | 20 headlines, 10 deduplicated clusters | `python scripts/fetch_public_snapshots.py` |

## Rules

- Do not edit `prices.csv` by hand; re-run the fetch script and keep the provenance file.
- Do not add a mechanism without a citation. The loader rejects mechanisms with no `citations`.
- Do not add an event without a source URL and a `session`; the event-study alignment depends on it.
- Do not commit `.cache/` (it is ignored).
- The Yahoo snapshot is **not** point-in-time. It is for reproducible evaluation, not production backtesting.

See `docs/data_sources.md` for access, revision behavior, point-in-time support and licensing.
