# FOMC statement snapshot

`statements_2000_2025.csv` is a subset of the public **FOMC Dataset** by HusseinKh90:

- Source repository: https://github.com/HusseinKh90/fomc-dataset
- Original documents: Federal Reserve FOMC statements (US government work, public domain)
- Subset: scheduled and intermeeting statements from 2000-01-01 to 2025-12-31
- Columns: `meeting_date`, `meeting_type`, `source_url`, `text`

The subset is bundled so that `scripts/build_fomc_events.py` can regenerate
`backend/data/events/fomc_generated.yaml` without network access. The generated
events are a homogeneous FOMC rate-change benchmark; they are not used to
re-label the curated event set.

## Parsing notes

- The target range is parsed from the statement text, not from a hard-coded
  meeting calendar.
- The change is the difference in the upper bound versus the prior statement.
- Only non-zero changes are emitted; holds are omitted from the homogeneous
  benchmark.
- Headlines are templated from the parsed range. The statement excerpt is kept
  as the summary.
- Surprise is `neutral` because no high-frequency Fed-funds/SOFR futures series
  is bundled. This is a known limitation of the benchmark.

## Caveats

- The upstream dataset is a scrape. The bundled subset is a snapshot, not a
  live feed. Re-run the upstream scraper if you need 2026+ statements.
- The `meeting_date` of an intermeeting statement can differ from the date in
  the source URL; the builder prefers the URL date when it can parse one.
- The text may contain mojibake from the upstream HTML; `scripts/build_fomc_events.py`
  repairs it with `ftfy` before parsing.
