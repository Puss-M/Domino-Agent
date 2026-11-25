# Contributing to Domino Agent

Thanks for taking the project seriously. This is a research prototype, so the bar is not “it runs” — it is “the claim is still true after your change.”

## Setup

```bash
git clone https://github.com/Puss-M/Domino-Agent.git
cd Domino-Agent
py -3.12 -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Run the checks:

```bash
ruff check . --select E9,F --extend-exclude frontend
pytest -q
```

Start the app:

```bash
uvicorn backend.main:app --reload
```

## Adding a mechanism

A mechanism is a hypothesis, not a prompt. Before adding one, answer:

1. What event type and direction triggers it?
2. Which conditions must hold, and which conditions exclude it?
3. Which transmission channels does it activate, with what sign?
4. What is the evidence grade, and why?
5. Which paper or official source supports the direction?

Add the entry to `backend/data/knowledge/mechanisms.yaml`:

```yaml
- id: UNIQUE_ID
  title: Short, falsifiable description
  event_types: [monetary_policy]
  directions: [tightening]
  actors: [US_FED]          # optional
  any_keywords: [ ... ]     # optional, all must have at least one hit
  none_keywords: [ ... ]    # optional, any hit excludes the mechanism
  confidence: 0.7
  evidence_grade: B
  horizon_days: 5
  rationale: "Why the channel signs follow."
  channels:
    real_yields: 0.8
    usd: 0.4
  citations:
    - "Author (Year), Journal"
```

Then:

- add a retrieval test in `tests/test_knowledge.py`;
- add a transmission assertion in `tests/test_transmission.py` if it changes an important asset;
- run `pytest`;
- run the backtest and update `docs/evaluation.md` if the numbers change.

Do **not** add a mechanism without a citation. Do not tune a mechanism against the test outcomes and then report the same test as out-of-sample.

## Adding an event

Add a dated entry to `backend/data/events/events.yaml` with:

- `date`, `time_et`, `session` (`before_open`, `during`, `after_close`, `non_trading`);
- `event_type`, `direction`, `actor`;
- a real headline and summary;
- `source_name`, `source_url`, `source_tier`;
- `magnitude` and `surprise` where applicable;
- `tags`.

Then add it to `tests/test_extractor.py` if it exercises a new pattern. Run the backtest and inspect whether the event has enough price history and whether the outcome window overlaps other events.

## Adding or rebuilding the FOMC benchmark

The FOMC split is generated, not hand-edited:

```bash
python scripts/build_fomc_events.py
python -m backend.app.cli events --dataset fomc
python -m backend.app.cli backtest --dataset fomc --window-end 1 --out backtest_fomc.json
```

- Source snapshot: `backend/data/fomc/statements_2000_2025.csv` (official statements, 2000–2025).
- The builder parses the target range, computes the change, repairs mojibake with `ftfy`, and rejects ambiguous changes that are not 25/50/75/100bp.
- 2000–2003 statements are excluded due to parsing artefacts.
- If you add a new statement, add a test in `tests/test_dataset.py` for the event count and tag.
- The FOMC split is a **stress test**, not an extraction benchmark. Templated headlines are excluded from `extraction.n`.

## Docker

```bash
docker build -t domino-agent .
docker run --rm -p 8000:8000 domino-agent
```

The image contains the bundled snapshots; it runs offline.

## Data refresh

```bash
python scripts/fetch_market_snapshot.py --start 2000-01-01
python scripts/fetch_public_snapshots.py
python scripts/build_fomc_events.py
```

- Yahoo adjusted closes are revised. Re-running the backtest after a refresh can change historical CARs.
- SEC asks for a contact string. Set `DOMINO_USER_AGENT` before bulk work.
- GDELT articles are a discovery layer; deduplicate before counting.

## Code style

- Python 3.10+, type hints where they clarify a contract.
- Prefer deterministic code for numbers. An LLM must never produce a numeric field that enters the graph.
- Keep the offline path working without an API key.
- Comments explain *why*, not *what*.
- Frontend is zero-build: no CDN, no bundler, no framework. Keep it that way unless there is a strong reason.

## Commit convention

Conventional Commits:

- `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

## Pull request checklist

- [ ] `ruff check . --select E9,F --extend-exclude frontend` passes.
- [ ] `pytest -q` passes.
- [ ] The offline demo still runs with no API key.
- [ ] If a number in the README changed, `docs/evaluation.md` was updated with the new value and the same protocol.
- [ ] New mechanisms have citations and a retrieval test.
- [ ] New events have a source URL and a session.
- [ ] If the benchmark changed, `docs/benchmark.md` and `docs/model_card.md` were updated.
- [ ] The FOMC negative result is still reported, not hidden.
- [ ] No claim of causal identification, trading alpha, or SOTA prediction was added.

## Research integrity

- Report failures. The FOMC negative skill, QQQ/XLU/FXI and 5-day results are in `docs/evaluation.md` for a reason.
- The FOMC stress test is a feature, not an embarrassment: it is the evidence that action-only priors need a surprise/positioning measure.
- Do not cherry-pick the test window.
- Do not call a curated label “ground truth” without qualification.
- Do not call a cited transmission hypothesis “causal inference” without an identification strategy.

## Reporting bugs

Include the command, the expected behavior, the actual behavior, and the Python version. If it is a data issue, include the snapshot date and the source.
