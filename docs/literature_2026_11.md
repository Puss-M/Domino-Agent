# Literature sweep — 2026-11-26

This note records a targeted sweep of recent work that could change Domino's
design, benchmark, or paper positioning. It is deliberately separate from
[`paper_outline.md`](paper_outline.md): the outline is the argument, this is the
evidence log.

## Access caveat

PaperDaily's API was **not reachable** from this machine at the time of the
sweep. `paperdaily.org` resolves to the fake-IP `198.18.0.15`; requests through
the local mihomo proxy fail at the TLS handshake, direct Cloudflare IPs are
blocked, and the PaperDaily web page hangs. No key was printed or stored.

The fallback was a domestic search path:

- Sogou mobile results (`wap.sogou.com`), which surface arXiv/alphaXiv/ChatPaper
  records with translated snippets;
- 360 Search (`so.com`), which indexes arXiv abstract pages and Chinese
  summaries;
- domestic mirrors (`intelliparadigm.com`, `cloud.baidu.com`, `juejin.cn`) for
  secondary summaries.

Consequently most entries below are **abstract/snippet-level**, not full-text
reads. IDs, titles and dates were cross-checked across at least two result
snippets where possible. Items marked "secondary" were only seen through a
Chinese summary. When PaperDaily is reachable again, the first task is to fetch
the full texts for the starred items.

## What is new (closest clusters)

### A. Symbolic causal graphs for finance

| Paper | ID / date | What it does (snippet-level) | Why it matters |
|---|---|---|---|
| *Online-Adaptive Fuzzy Cognitive Maps for Neuro-symbolic Financial Forecasting* — Brandon Rodriguez, Abel Deulofeu, Olaoluwa Adigun et al. | arXiv 2611.13388, 2026-11-10 | Pairs online-adaptive Fuzzy Cognitive Maps with an LSTM for regime-shifting financial series; Framework I builds the FCM from dual-source price series and macro indicators. | Closest modeling neighbor. FCMs are interpretable weighted causal graphs; they do **not** return a solver proof core or a structural ambiguity status. |
| *Causal Autoencoder-like Generation of Feedback Fuzzy Cognitive Maps with an LLM Agent* — Panda, Adigun & Kosko | arXiv 2509.25593, 2025-09-29 | Uses an LLM agent to generate feedback FCMs. | Shows the "LLM builds the causal graph" pattern is already active; our novelty must be the verification layer, not graph construction alone. |
| *The Agentic Leash: Extracting Causal Feedback Fuzzy Cognitive Maps with LLMs* | arXiv 2601.00097, 2025-12-31 | LLM extraction of causal feedback FCMs. | Same conclusion; also a useful phrase for "keep the LLM on a leash" in the paper. |
| *RICE-Alpha: Reliability-Informed Correction with Event Graphs for LLM-Agent Stock Forecasting* | arXiv 2609.34004, 2026-09-27 | Point-in-time stock-scoring framework separating a history-aware multi-agent component from event-graph correction. | Closest empirical design: event graph + point-in-time + LLM agents. It scores stocks; we test macro transmission signs and report a negative FOMC boundary. |
| *Structured Event Representation and Stock Return Predictability* — Gang Li, Dandan Qiao, Mingxuan Zheng | arXiv 2512.19484, 2025-12-22 | LLM-extracted event features are effective for text-based stock return prediction; proposes a deep model over structured event representations. | Supports the event-driven premise and gives a benchmark-style citation for "event features predict returns". |

### B. Verification, provenance and compliance

| Paper | ID / date | What it does (snippet-level) | Why it matters |
|---|---|---|---|
| *FinVerify: A Verification Framework for Financial Agents* | arXiv 2611.20423, 2026-11-16 | Operationalizes source fidelity, comparability, accounting integrity and financial-model fidelity as verification protocols. | Closest "verification framework" competitor. Our claim must be narrower: sign structure of macro transmission, not general financial-answer verification. |
| *NumTrace: Auditing the Number Provenance of Financial Analyst Agents* | arXiv 2610.34887, 2026-10-26 | Audits whether a number in an agent output refers to the right entity, concept, period, unit and scope; reference-answer checks can miss these. | Directly motivates **P-013**: value-only grounding is insufficient. A number can be right and still be wrong. |
| *GURU: A Hierarchical Neuro-Symbolic Multi-Agent System for Verification-Aware Automation* | arXiv 2611.01001, 2026-10-31 | Hierarchical neuro-symbolic multi-agent system; framing: an AI may find a safe action, but must never decide what counts as safe. | Validates the "verifier owns the safety predicate" architecture. Use the framing in the introduction. |
| *NSVIF: Neuro-Symbolic Verification on Instruction Following of LLMs* | arXiv 2601.17789, 2026-01-25 | Neuro-symbolic framework for verifying whether an LLM output follows the prompt's constraints; VifBench. | Adjacent to P-001..P-013: compile natural-language constraints and check outputs. |
| *Neuro-Symbolic Agents for Hallucination-Free Requirements Reuse* — Ahmed F. Ibrahim | arXiv 2605.01562, 2026-05-02 | Neuro-symbolic agents for requirements reuse, targeting structurally invalid or inconsistent combinations. | Same "LLM proposes, symbolic layer rejects" pattern outside finance; useful related work. |
| *VA-NSF: verifier–executor neuro-symbolic framework for LLM-driven internet financial transaction constraint verification* | secondary, 2026-08-07 | Two-layer architecture separating natural-language understanding from formal constraint execution; neural executor uses grammar-constrained decoding. | Very close to our policy gate, but for transaction execution. Cite as evidence that the pattern is converging in finance. |
| *FinVeriQA: Financial Research Agents for QA — Routing, Retrieval, MCP Tool Use, and Provenance-Aware Evidence Verification* | arXiv 2611.25071, 2026-11-18 | Tests self-consistency under shared-evidence errors; agreement stays high while accuracy collapses. | Strong support for "debate/self-consistency is not verification". Use in the multi-agent motivation. |
| *ADAM* — `adamvangrover/adam` (GitHub, early project) | secondary, 2026-08 | "Institutional-grade neuro-symbolic multi-agent AI framework" for credit risk, financial modeling and deterministic workflow orchestration. | A competitor signal, but early (reported ~4 stars). Differentiate with public benchmark, proof cores, and documented negative results. |

### C. Temporal integrity and lookahead

| Paper | ID / date | What it does (snippet-level) | Why it matters |
|---|---|---|---|
| *Detecting Lookahead Bias in LLM Forecasts* — Zhenyu Gao, Wenxi Jiang, Yutong Yan | arXiv 2512.23847, 2025-12-29 | Statistical procedure to detect lookahead bias in LLM-generated economic forecasts; uses model recall of future information. | The cleanest citation for "LLM backtests can leak the future". |
| *Temporal Leakage in LLM Backtesting: Measurement, Validation, and Adjusted Scores* — Zeyu Zhang, Bradly C. Stadie | arXiv 2608.02985, 2026-08-04 | Measures and validates temporal leakage; proposes adjusted scores. | A reviewer will ask for this. Our LLM-free metric path is an advantage, but revised market data remains a caveat. |
| *FinCutBench: A Continually Updated Benchmark for Measuring the Temporal Boundaries of LLM Financial Knowledge* | arXiv 2611.11588, 2026-11-08 | Continually updated benchmark for parametric look-ahead in financial knowledge, e.g. asking for a quarter's actual EPS. | Benchmark-level evidence that temporal boundaries are now a first-class evaluation object. |
| *When Does Post-Call Begin? An Availability Contract for Earnings-Call NLP Benchmarks* | arXiv 2610.21659, 2026-10-15 | Defines an availability contract for when earnings-call text becomes usable. | A concrete template for a "point-in-time contract" per data source. |
| *LLMs Don't Know What They Know: Benchmarking Temporal Self-Knowledge for Financial Backtesting* | arXiv 2611.06808, 2026-11-04 | Tests whether models know what they know about the future; temporal self-knowledge. | Another citation for the temporal-integrity section. |

### D. Financial-agent benchmarks

| Paper | ID / date | What it evaluates | Relation to DMB |
|---|---|---|---|
| *Fin-RATE* | arXiv 2602.07294, 2026-02 | Real-world financial analytics/tracking on SEC filings; hallucination categories include numeric/categorical and entity-attribute errors. | QA/filing benchmark; DMB is a macro event-study benchmark. Complementary. |
| *FinFIRST* | arXiv 2609.25192, 2026-09-21 | Search agents: retrieval, sourcing and traceability. | Retrieval benchmark; not a transmission benchmark. |
| *FinHopper* | arXiv 2610.26036, 2026-10-19 | Progressive multi-hop financial agent tasks with step-wise evaluation. | Agentic QA; complementary. |
| *AgenticFinBench* | arXiv 2611.04813, 2026-11-03 | Diverse real-world financial agent requests. | Agentic task benchmark; complementary. |
| *FinAutoRubric* | arXiv 2609.35744, 2026-09-28 | Expert-guided automatic rubric generation for financial research agents. | Evaluation methodology; could inform our paper's artifact appendix. |

## Six lessons

1. **Verification is the new battleground, but the layers differ.** FinVerify
   verifies financial answers; NumTrace verifies number provenance; GURU
   verifies mission-critical actions; NSVIF verifies instruction following;
   VA-NSF verifies transaction constraints. Domino verifies **the sign
   structure of a macro transmission graph**. That is a defensible, narrower
   layer — but the paper must say so explicitly, or reviewers will read
   "verification" as a crowded claim.

2. **Number provenance is not value matching.** NumTrace's taxonomy (entity,
   concept, period, unit, scope) exposes a real gap in P-004. A number can be
   traceable and still wrong. We added **P-013** for unit/dimension grounding
   and a sixth injection type; the audit now detects **60/60** corruptions with
   **0/10** clean false positives. Period/entity/scope checks remain future
   work.

3. **Temporal leakage is now a benchmark problem, not a footnote.** Gao et al.,
   Zhang & Stadie, FinCutBench and the availability-contract paper all target
   it. Domino's offline path has no LLM in the metric path, so it avoids
   parametric leakage by construction. The remaining exposure is revised market
   data (Yahoo adjusted closes) and editorial labels. The paper should add a
   **point-in-time contract** table per source and a short "what could still
   leak" subsection.

4. **Event graphs and FCMs are the closest modeling family.** RICE-Alpha and the
   FCM line already combine event/causal graphs with learning. Our difference is
   not "we have a graph"; it is **qualitative sign algebra + SMT proof cores +
   ambiguity as a first-class output**. The paper should cite FCMs and
   RICE-Alpha directly and explain why a weighted graph does not answer "which
   minimal set of mechanisms entails this sign, and where is the sign genuinely
   ambiguous?".

5. **Cross-asset dependence needs dependence-aware inference.** E7's
   Kolari–Pynnönen adjustment and event-clustered bootstrap are aligned with the
   event-study literature. The new agent benchmarks mostly evaluate QA accuracy;
   they do not solve the cross-asset dependence problem. This is a small but
   real methodological contribution.

6. **Multi-agent debate is not verification.** FinVeriQA's shared-evidence
   result (self-consistency stays confident while accuracy collapses) is another
   data point for the paper's motivation. GURU's framing — the AI may propose a
   safe action but must not define safety — is the cleanest one-line statement
   of our policy gate.

## What changed in the repository

- **P-013** (`backend/app/symbolic/policy.py`): every unit-bearing number in the
  narrative must match the structured unit. A grounded 50bp written as "50
  percent" now fails.
- **Signed-number parsing** (`backend/app/nlp/numbers.py`): `parse_numbers` now
  preserves a leading `+`/`-`. This was a latent bug: `-234bp` was parsed as
  `234bp`, which made P-013 unable to see negative memo values.
- **E5 audit** (`scripts/hallucination_audit.py`): six corruption types,
  60 injected cases, 60/60 detected, 0/10 clean false positives.
- **Docs**: P-001–P-013 across README, methodology, model card, neuro-symbolic
  design and resume bullets; paper-related-work section extended with the new
  clusters.

## What to do next

**P0 — paper credibility**

1. Add a **point-in-time contract** table: for each data source, the timestamp
   at which the value became public, and whether the benchmark uses a revised
   value. Cite Gao et al. (2512.23847), Zhang & Stadie (2608.02985),
   FinCutBench (2611.11588) and the availability-contract paper (2610.21659).
2. Add **FCM and RICE-Alpha** to the paper's closest-work paragraph and explain
   the difference in one sentence each.
3. Add **FinVerify / NumTrace** to the verification paragraph; state that Domino
   verifies transmission signs, not answers or filings.

**P1 — stronger system**

4. Extend P-013 to **period/entity/scope**: each memo number should carry a
   reference to the structured field (value, unit, period, entity), not just a
   dimensional check. This is the NumTrace agenda applied to our memo.
5. Add a **temporal integrity audit** to the benchmark: fail if any input used
   for an event was published after the event's decision time; report the
   share of revised vs point-in-time series.
6. Consider an **FCM baseline** on the curated benchmark. It would test whether
   a learned weighted graph beats our qualitative mechanism graph — a useful
   adversarial baseline, not a required one.

**P2 — paper experiments**

7. E6 ablation (numeric-only vs symbolic-only vs symbolic-gated) remains the
   highest-value missing experiment.
8. E10 monetary/information decomposition remains the scientifically strongest
   extension, but needs intraday rate-equity data.

## Uncertainties

- Full texts were not read for most entries; the table records what the search
  index and secondary summaries said, not a verified methods section.
- The FCM author list is truncated in the snippet; the paper should confirm the
  complete author list from arXiv.
- VA-NSF was only seen through a Chinese summary; its venue, authors and exact
  title need verification.
- `ADAM` is an early GitHub project (secondary report: ~4 stars); treat it as a
  positioning signal, not a peer-reviewed baseline.
- Some snippet dates are search-index dates, not arXiv submission dates. The
  IDs and titles are the stable identifiers.

## Search log (selected)

Queries included: `neuro-symbolic finance`, `Online-Adaptive Fuzzy Cognitive
Maps`, `VA-NSF 神经符号 互联网金融`, `FinVerify financial agents`, `NumTrace
number provenance`, `RICE-Alpha event graphs`, `Structured Event Representation
stock returns`, `Detecting Lookahead Bias LLM Forecasts`, `Temporal Leakage LLM
Backtesting`, `Fin-RATE SEC filings`, `FOMC 文本 大模型 资产`, `事件研究
大语言模型`, `SMT 金融 形式化 验证`, `金融 合规 大模型 约束 验证`.

When PaperDaily is reachable again, rerun the same queries there and replace
snippet-level notes with full-text notes for the starred items: 2611.13388,
2609.34004, 2512.19484, 2611.20423, 2610.34887, 2611.01001, 2512.23847,
2608.02985, 2602.07294.
