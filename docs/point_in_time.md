# Point-in-time contract (E11)

The benchmark is **not** a point-in-time reconstruction. This page makes that
explicit instead of hiding it in a footnote.

The contract is machine-readable at
[`backend/data/point_in_time.yaml`](../backend/data/point_in_time.yaml). It is a
declaration, not a live vintage feed: a source is only `point_in_time: yes` if
the project actually stores a vintage.

## What the contract says

| Source | Used in | Available at | Revision | Point-in-time |
|---|---|---|---|---|
| Yahoo Finance adjusted close | all | after the US close | adjusted retroactively for splits/dividends | **no** |
| Curated macro labels | curated, extended | editorial `published_at` | hand-edited | **editorial** |
| FOMC statements | fomc, fomc_surprise, extended | 14:00 ET on statement date | statements immutable; compilation can update | **partial** |
| Bu–Rogers–Wu surprises | fomc_surprise | published ex post (2021) | upstream series can be revised | **ex post** |
| SEC EDGAR / XBRL | examples only | filing acceptance | filings immutable; XBRL can be restated | partial |
| GDELT | discovery only | ~15 minutes | URLs are not permanent | no |
| FRED / ALFRED | optional | release calendar | ALFRED exposes vintages | yes |
| US Treasury | cross-check only | end of day | rare | no |
| World Bank | regime context only | annual/quarterly | revised | no |

## The verdict

For every benchmark the audit returns `verdict: not_point_in_time`, with the
dataset-specific culprit list:

| Dataset | Revised / ex-post inputs |
|---|---|
| Curated | Yahoo prices, editorial labels |
| FOMC action-only | Yahoo prices, FOMC compilation |
| FOMC surprise-aware | Yahoo prices, FOMC compilation, BRW ex-post series |
| Extended | Yahoo prices, editorial labels, FOMC compilation |

This is intentionally conservative. The LLM-free metric path removes
**parametric** lookahead — there is no model that memorised the future — but it
does not remove **data revision** leakage. The honest statement is:

> The engine has no LLM in the metric path, so it is not exposed to the
> parametric lookahead documented by Gao et al. (2025) and Zhang & Stadie
> (2026). The prices and labels are still revised snapshots, so the benchmark is
> not a point-in-time reconstruction.

## Checks

`audit_point_in_time` returns these checks:

| Check | Current result | Meaning |
|---|---|---|
| `no_llm_metric_path` | pass | rules + deterministic transmission + event study only |
| `event_timestamps_present` | pass | every event has an editorial timestamp |
| `labels_frozen` | fail | curated labels are hand-edited |
| `prices_point_in_time` | fail | Yahoo adjusted closes are revised |
| `surprises_point_in_time` | fail | BRW is an ex-post published series |
| `events_within_price_snapshot` | pass | latest event ≤ price snapshot end |

## Reproduce

```bash
python scripts/point_in_time_audit.py
# writes docs/results/point_in_time.json
```

API:

```text
GET /api/point-in-time?dataset=curated|fomc|fomc_surprise|extended
```

## What would make it a pass

1. Replace Yahoo adjusted closes with an as-traded, unadjusted price archive
   plus a separate corporate-action table.
2. Freeze the curated labels with a versioned, timestamped release.
3. Replace the BRW ex-post series with a real-time surprise feed (or an
   intraday rate-implied surprise computed at the statement time).
4. Store the FOMC statement text and target range as separate vintages.

Until then, the benchmark's claim is about **mechanism-level directional
skill**, not about a deployable point-in-time trading signal.

## References

- Gao, Jiang & Yan, *Detecting Lookahead Bias in LLM Forecasts*, arXiv 2512.23847 (2025-12-29).
- Zhang & Stadie, *Temporal Leakage in LLM Backtesting*, arXiv 2608.02985 (2026-08-04).
- *FinCutBench*, arXiv 2611.11588 (2026-11-08).
- *When Does Post-Call Begin? An Availability Contract for Earnings-Call NLP Benchmarks*, arXiv 2610.21659 (2026-10-15).
