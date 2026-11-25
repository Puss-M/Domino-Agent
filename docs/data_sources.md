# Data sources

The repository is designed to run offline from small, redistributable snapshots. The connectors exist so the same interfaces can be refreshed with live data without changing the reasoning code.

## Catalog

| ID | Source | Used for | Access | Frequency | Revision | Point-in-time |
|---|---|---|---|---|---|---|
| `sec` | SEC EDGAR submissions, XBRL company facts, 8-K exhibits | Financial statement facts, filing text | No key; declared User-Agent; <10 req/s | Event-driven | Filings immutable; XBRL values can be restated | Partial: the `filed` field enables as-filed reconstruction |
| `gdelt` | GDELT 2.0 DOC API | Headline discovery, deduplication | No key; fair use | ~15 minutes | Articles re-crawled; URLs not permanent | No explicit vintage; cache `seendate` |
| `treasury` | US Treasury daily yield curve | Rate context, cross-checks | No key | Daily | Rare | No; snapshot |
| `fred` | FRED / ALFRED | Macro series, vintage-aware | `FRED_API_KEY` | Daily–quarterly | Yes | **Yes**, `realtime_start` / `realtime_end` |
| `worldbank` | World Bank Indicators API | Annual regime context | No key | Annual/quarterly | Yes | No |
| `yahoo` | Yahoo Finance chart API | Event-window ETF outcomes | No key; convenience endpoint | Daily | Adjusted prices revised after splits/dividends | No |

The machine-readable version is served at `GET /api/data-sources`.

## What is bundled

| Path | Contents | Refresh |
|---|---|---|
| `backend/data/market/prices.csv` | 12 ETFs, daily adjusted close, 2015–present, plus `provenance.json` | `python scripts/fetch_market_snapshot.py --start 2015-01-01` |
| `backend/data/macro/treasury_yields_2024.csv` | 250 daily Treasury curves | `python scripts/fetch_public_snapshots.py` |
| `backend/data/sec/aapl_sample.json` | One 8-K exhibit (truncated) + 12 XBRL revenue observations | `python scripts/fetch_public_snapshots.py` |
| `backend/data/news/gdelt_fed_sample.json` | 20 GDELT headlines and 10 deduplicated clusters | `python scripts/fetch_public_snapshots.py` |

The event labels and the mechanism library are curated, not downloaded:
`backend/data/events/events.yaml` and `backend/data/knowledge/mechanisms.yaml`.

## Practical notes

### SEC EDGAR

- The SEC requires a descriptive `User-Agent` with contact information. The default is a placeholder; set `DOMINO_USER_AGENT` to your own contact for bulk work.
- Stay below 10 requests/second. `SecEdgar.min_interval = 0.13` enforces ~7.7 req/s.
- `data.sec.gov` and `www.sec.gov` use different hostnames. Do not pin a `Host` header on the shared session.
- `company_facts` preserves the `filed` date, which is what makes as-filed reconstruction possible. A convenience price/fundamental API that only returns the latest value does not.
- The 8-K exhibit in the snapshot may be a debt issuance rather than an earnings release. The connector exposes the text; the demo does not claim that every 8-K is an earnings release.

### GDELT

- The DOC article list returns titles, URLs, domains, languages and `seendate`; it does not return article bodies.
- Deduplicate before counting. The bundled sample turns 20 headlines into 10 clusters.
- Source tier matters: a central-bank statement and a syndicated aggregator are not equivalent evidence.

### FRED / ALFRED

- `FRED_API_KEY` is required. Without it, the connector raises a clear `DataSourceError` and the rest of the project still runs.
- For a point-in-time backtest, pass a vintage date to `Fred.series(..., vintage="2022-06-10")`. The `realtime_start/realtime_end` parameters are the reason ALFRED is the preferred macro source.
- FRED endpoint availability varies by network; the offline path never depends on it.

### World Bank

- Annual data is for regime context only. It is not an event-study input.
- Values are revised; archive a snapshot if you need historical vintages.

### Yahoo Finance

- This is a convenience endpoint, not an exchange feed. It can rate-limit (`HTTP 429`) and it can revise adjusted closes after corporate actions.
- The price snapshot is explicitly not point-in-time. A production event study should use CRSP/Compustat or a vendor with vintages.
- The `provenance.json` records the endpoint, retrieval time, requested window, tickers, row counts and caveats.

### Loughran–McDonald dictionary

The full LM master dictionary is not redistributed. The repository ships a small seed lexicon. If you have a licensed copy, set:

```bash
export DOMINO_LM_DICTIONARY=/path/to/LoughranMcDonald_MasterDictionary.csv
```

The loader merges `Positive`, `Negative`, `Uncertainty`, `StrongModal` and `WeakModal` flags.

### Treasury

- The daily yield-curve CSV is public domain.
- It is a snapshot; the current project uses it for context and cross-checks, not for the event-study outcome.

## Licensing summary

- **Code**: MIT.
- **US government data** (SEC, Treasury): public domain.
- **World Bank**: CC BY 4.0.
- **GDELT**: GDELT terms; research/academic use.
- **Yahoo**: Yahoo terms; research/educational use only.
- **FRED**: FRED terms; attribution required.
- **Loughran–McDonald**: licensed separately; not included.

If you republish the snapshots, keep the provider attribution and the caveats in `provenance.json`.
