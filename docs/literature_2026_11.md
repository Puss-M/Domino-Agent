# Literature sweep — 2026-11-26

This note records a targeted sweep of recent work that could change Domino's
design, benchmark, or paper positioning. It is deliberately separate from
[`paper_outline.md`](paper_outline.md): the outline is the argument, this is the
evidence log.

## Access caveat

PaperDaily was **initially unreachable** from this machine: `paperdaily.org`
resolved to the fake-IP `198.18.0.15`, the local mihomo proxy reset the TLS
handshake, and direct Cloudflare IPs were blocked. The first pass therefore used
Sogou mobile (`wap.sogou.com`), 360 Search (`so.com`) and domestic mirrors
(`intelliparadigm.com`, `cloud.baidu.com`, `juejin.cn`) for discovery. No key was
printed or stored.

PaperDaily recovered later on 2026-11-26 (HTTP 200), and arXiv became reachable.
The final pass is **abstract-level**, not snippet-level: 16 key papers were
fetched from arXiv with title, authors, date and abstract; six also have a
PaperDaily detail record with DOI (FCM, FinVerify, NumTrace, FAAB, LLM-FCM,
XNSTL). The verified abstracts are stored in
[`results/arxiv_abstracts_2026_11.json`](results/arxiv_abstracts_2026_11.json).

Two entries remain **secondary** and are marked as such: VA-NSF (Chinese
summary only) and ADAM (early GitHub project). Full PDFs were not read, so
method details beyond the abstract are still open.

## What is new (closest clusters)

### A. Symbolic causal graphs for finance

| Paper | ID / date | What it does (snippet-level) | Why it matters |
|---|---|---|---|
| *Online-Adaptive Fuzzy Cognitive Maps for Neuro-symbolic Financial Forecasting* — Brandon Rodriguez, Abel Deulofeu, Olaoluwa Adigun | arXiv 2611.13388, 2026-11-10; ICMLA 2026, DOI 10.1109/ICMLA69890.2026.00220 | Framework I builds an FCM from live dual-source price series and macro indicators and adapts its edges online with an error-driven Hebbian rule; Asymmetric Additive Residual Fusion combines the symbolic and LSTM signals. | Closest modeling neighbor. FCMs are interpretable weighted causal graphs with dynamics; they do **not** return a solver proof core or a structural ambiguity status. |
| *Causal Autoencoder-like Generation of Feedback Fuzzy Cognitive Maps with an LLM Agent* — Panda, Adigun & Kosko | arXiv 2509.25593, 2025-09-29 | An LLM maps a feedback FCM into text and reconstructs the FCM from that text, approximating an identity map; both encoder and decoder explain their decisions. | Shows the "LLM builds the causal graph" pattern is already active; our novelty must be the verification layer, not graph construction alone. |
| *The Agentic Leash: Extracting Causal Feedback Fuzzy Cognitive Maps with LLMs* — Panda, Adigun & Kosko | arXiv 2601.00097, 2025-12-31 | An LLM agent extracts causal feedback FCMs from raw text; the FCM's equilibria drive the agents to fetch and process more causal text, which can modify the adaptive graph. | Same conclusion; also a useful phrase for "keep the LLM on a leash" in the paper. |
| *RICE-Alpha: Reliability-Informed Correction with Event Graphs for LLM-Agent Stock Forecasting* — Tong Liu, Lanmiao Liu, Xiang Hu | arXiv 2609.34004, 2026-09-27 | A point-in-time stock-scoring framework that models issuer-specific event chronology, information availability and transition reliability; separates a history-aware multi-agent component from event-graph correction. | Closest empirical design: event graph + point-in-time + LLM agents. It scores stocks; we test macro transmission signs and report a negative FOMC boundary. |
| *Structured Event Representation and Stock Return Predictability* — Gang Li, Dandan Qiao, Mingxuan Zheng | arXiv 2512.19484, 2025-12-22 | A pre-trained LLM extracts event features from news; an SER + attention model predicts cross-sectional stock returns and outperforms comparators. | Supports the event-driven premise and gives a benchmark-style citation for "event features predict returns". |
| *Construction of Fuzzy Cognitive Maps assisted by AI (LLM): methodological process and financial use case* | 2026-06-17, DOI 10.5281/zenodo.20724740 | Three phases: concept elicitation via structured prompts to multiple AIs; interactive correction, weighting and grouping; generation/combination/export of the FCM. | Directly relevant to how our cited mechanism library could be authored or audited with an LLM; it still does not certify the resulting graph. |

### B. Verification, provenance and compliance

| Paper | ID / date | What it does (snippet-level) | Why it matters |
|---|---|---|---|
| *FinVerify: A Verification Framework for Financial Agents* — Mao Guan, Qian Chen, Ge Meng, Xiao-Yang Liu | arXiv 2611.20423, 2026-11-16 | From 190 incorrect trajectories in the Agent Finance Reasoning dataset, defines five error categories — temporal integrity, source fidelity, comparability, accounting integrity, financial-model fidelity — and operationalizes them as verification protocols; an LLM structures claims while deterministic validators check the finance. | Closest "verification framework" competitor. Our claim must be narrower: sign structure of macro transmission, not general financial-answer verification. |
| *NumTrace: Auditing the Number Provenance of Financial Analyst Agents* — Tianlei Zhu, Matt White, Xue Liu, Xiao-Yang Liu | arXiv 2610.34887, 2026-10-26 | A 540-question benchmark over 2,163 SEC EDGAR documents (Form 13F and Item 402(i)); audits whether each numerical claim has the right source and financial semantics — entity, concept, period, unit, scope. | Directly motivates **P-013**: value-only grounding is insufficient. A number can be right and still be wrong. |
| *GURU: A Hierarchical Neuro-Symbolic Multi-Agent System for Verification-Aware Automation* — Allan Grosvenor et al. | arXiv 2611.01001, 2026-10-31 | A partition of authority: learned models propose/rank/accelerate; a symbolic rules engine checks every consequential action against hard limits before execution; validated physics/engineering constraints. | Validates the "verifier owns the safety predicate" architecture. Use the framing in the introduction. |
| *NSVIF: Neuro-Symbolic Verification on Instruction Following of LLMs* — Yiming Su et al. | arXiv 2601.17789, 2026-01-25 | Neuro-symbolic framework for verifying whether an LLM output follows the prompt's constraints, with VifBench; violations can propagate along agentic reasoning chains. | Adjacent to P-001..P-013: compile natural-language constraints and check outputs. |
| *Neuro-Symbolic Agents for Hallucination-Free Requirements Reuse* — Ahmed F. Ibrahim | arXiv 2605.01562, 2026-05-02 | Neuro-symbolic agents for requirements reuse, targeting structurally invalid or inconsistent combinations. | Same "LLM proposes, symbolic layer rejects" pattern outside finance; useful related work. |
| *VA-NSF: verifier–executor neuro-symbolic framework for LLM-driven internet financial transaction constraint verification* | secondary, 2026-08-07 | Two-layer architecture separating natural-language understanding from formal constraint execution; neural executor uses grammar-constrained decoding. | Very close to our policy gate, but for transaction execution. Cite as evidence that the pattern is converging in finance. |
| *FinVeriQA: Financial Research Agents for QA — Routing, Retrieval, MCP Tool Use, and Provenance-Aware Evidence Verification* — Meenakshi Rajpurohit et al. | arXiv 2611.25071, 2026-11-18 | An open-source multi-agent QA prototype over SEC filings and live market data; a typed-decision router assigns each question; tests shared-evidence errors where self-consistency stays confident while accuracy collapses. | Strong support for "debate/self-consistency is not verification". Use in the multi-agent motivation. |
| *FAAB: A Benchmark for Fault Detection and Responsibility Attribution in Financial Multi-Agent Workflows* | 2026-11-14, DOI 10.1145/3858063.3858684 | 300 real point-in-time SEC and I/B/E/S workflows, 300 clean controls and 700 minimal single-point interventions over 14 fault classes; given a typed workflow trace, detect the fault, classify root cause, and localize the earliest responsible agent/step. | The closest audit benchmark. Our ledger records what happened; FAAB asks who broke the chain first. This is the natural extension of our audit trail. |
| *Neuro-Symbolic AI for Secure, Explainable, and Intelligent Banking and FinTech Systems* | 2026-11-07, DOI 10.36347/sjet.2026.v14i11.001 | Proposes XNSTL, an Explainable Neuro-Symbolic Trust Layer integrating LLM learning with symbolic rule reasoning and a financial ontology for fraud, credit risk, forecasting and transaction security. | A broad framework paper; useful for the compliance motivation, not a macro event-study benchmark. |
| *ADAM* — `adamvangrover/adam` (GitHub, early project) | secondary, 2026-08 | "Institutional-grade neuro-symbolic multi-agent AI framework" for credit risk, financial modeling and deterministic workflow orchestration. | A competitor signal, but early (reported ~4 stars). Differentiate with public benchmark, proof cores, and documented negative results. |

### C. Temporal integrity and lookahead

| Paper | ID / date | What it does (snippet-level) | Why it matters |
|---|---|---|---|
| *Detecting Lookahead Bias in LLM Forecasts* — Zhenyu Gao, Wenxi Jiang, Yutong Yan | arXiv 2512.23847, 2025-12-29 | A date-only recall query for a firm-date pair estimates the probability that the LLM internalized the realized outcome — the Lookahead Propensity (LAP); LAP is positive in-sample and collapses out-of-sample. | The cleanest citation for "LLM backtests can leak the future". |
| *Temporal Leakage in LLM Backtesting: Measurement, Validation, and Adjusted Scores* — Zeyu Zhang, Bradly C. Stadie | arXiv 2608.02985, 2026-08-04 | Shows the standard before/after-cutoff check is uninformative; recency mimics leakage because models legitimately know more near their cutoff; proves no passive backtest fix and proposes adjusted scores. | A reviewer will ask for this. Our LLM-free metric path is an advantage, but revised market data remains a caveat. |
| *FinCutBench: A Continually Updated Benchmark for Measuring the Temporal Boundaries of LLM Financial Knowledge* — Siyuan Li et al. | arXiv 2611.11588, 2026-11-08 | A continually updated monthly benchmark (9,000 questions) measuring how far a fixed model's financial knowledge extends over calendar time; targets parametric look-ahead. | Benchmark-level evidence that temporal boundaries are now a first-class evaluation object. |
| *When Does "Post-Call" Begin? An Availability Contract for Earnings-Call NLP Benchmarks* — Xiaoyu Ma et al. | arXiv 2610.21659, 2026-10-15 | Identifies within-event timing mismatch: announcements, prepared remarks and discussion span multiple high-frequency return intervals; chronological splits do not prevent the target from starting before the input is complete. | A concrete template for a "point-in-time contract" per data source. |
| *LLMs Don't Know What They Know: Benchmarking Temporal Self-Knowledge for Financial Backtesting* | arXiv 2611.06808, 2026-11-04 | Tests whether models know what they know about the future; temporal self-knowledge. | Another citation for the temporal-integrity section. |

### D. Financial-agent benchmarks

| Paper | ID / date | What it evaluates | Relation to DMB |
|---|---|---|---|
| *Fin-RATE* — Yidong Jiang et al. | arXiv 2602.07294, 2026-02 | A real-world financial analytics/tracking benchmark on SEC filings, requiring synthesis across documents, reporting periods and entities; hallucination categories include numeric/categorical and entity-attribute errors. | QA/filing benchmark; DMB is a macro event-study benchmark. Complementary. |
| *FinFIRST* | arXiv 2609.25192, 2026-09-21 | Search agents: retrieval, sourcing and traceability. | Retrieval benchmark; not a transmission benchmark. |
| *FinHopper* | arXiv 2610.26036, 2026-10-19 | Progressive multi-hop financial agent tasks with step-wise evaluation. | Agentic QA; complementary. |
| *AgenticFinBench* | arXiv 2611.04813, 2026-11-03 | Diverse real-world financial agent requests. | Agentic task benchmark; complementary. |
| *FinAutoRubric* | arXiv 2609.35744, 2026-09-28 | Expert-guided automatic rubric generation for financial research agents. | Evaluation methodology; could inform our paper's artifact appendix. |

### E. Monetary-policy surprises and event-level returns

| Paper | ID / date | What it does (abstract-level) | Why it matters |
|---|---|---|---|
| *Supply-Side Information and Monetary Policy Surprises* | SSRN 7633199, 2026-10-20, DOI 10.2139/ssrn.7633199 | Shows supply conditions also enter high-frequency policy surprises, revealed by interest-rate and exchange-rate comovement; when a supply shock hits and the Fed tolerates supply-driven inflation, surprises signal higher medium-term rates and dollar depreciation. | Directly relevant to E9/E10. The missing input is not a two-way monetary/information split but a **three-way monetary / information / supply** decomposition. |
| *METT: High-Frequency Return Forecasting from Event Streams* | 2026-11-14, DOI 10.1145/3858063.3858779 | One-second event-level return forecasting from NYSE TAQ streams; a shared cross-stock transformer encodes event types and elapsed time, with next-arrival supervision and stock-specific thresholds. | Adjacent high-frequency event model. It reinforces that event-time modeling is a distinct forecasting problem, but it is intraday and not a macro transmission benchmark. |
| *Reinforcement Learning with LLM-Generated Event-Based Sentiment Index for Adaptive Model Selection* | SSRN 7291625, 2026-08-15, DOI 10.2139/ssrn.7291625 | An RL meta-controller allocates across base models using a novel Event-Based Synthetic Stock Sentiment Index generated by an LLM (baseline, event shocks, sector trends, noise). | Shows event-based LLM signals being used for model selection rather than direction; useful adjacent work, not a direct baseline. |

## Seven lessons

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

7. **The FOMC surprise decomposition is three-way, not two-way.** The 2026
   supply-side paper (SSRN 7633199) shows that supply conditions enter
   high-frequency policy surprises through rate–exchange-rate comovement. The
   next FOMC experiment should separate **monetary, information and supply**
   components, not just monetary vs information; the rates-only decomposition of
   Jarociński–Karadi is a starting point, not the end state.

## What changed in the repository

- **P-013** (`backend/app/symbolic/policy.py`): every unit-bearing number in the
  narrative must match the structured unit. A grounded 50bp written as "50
  percent" now fails.
- **Signed-number parsing** (`backend/app/nlp/numbers.py`): `parse_numbers` now
  preserves a leading `+`/`-`. This was a latent bug: `-234bp` was parsed as
  `234bp`, which made P-013 unable to see negative memo values.
- **E5 audit** (`scripts/hallucination_audit.py`): six corruption types,
  60 injected cases, 60/60 detected, 0/10 clean false positives.
- **E11 point-in-time contract** (`backend/data/point_in_time.yaml`,
  `backend/app/evaluation/temporal.py`, `/api/point-in-time`): every benchmark
  now returns a dataset-specific `not_point_in_time` verdict with the culprit
  list. The LLM-free metric path removes parametric lookahead, not data
  revision leakage.
- **E6 symbolic ablation** (`backend/app/evaluation/backtest.py`): numeric-only,
  symbolic-only, symbolic-gated and symbolic-blend arms. The result is a
  **negative ablation for predictive skill** — blend vs numeric ΔBrier −0.0002
  (curated) / +0.0025 (FOMC), neither significant. The symbolic layer's value is
  auditability and structured ambiguity, not accuracy.
- **P-008 fix**: the policy now catches a numeric direction that contradicts a
  *proved* symbolic claim, not only a `not_entailed` status.
- **Docs**: P-001–P-013 across README, methodology, model card, neuro-symbolic
  design and resume bullets; paper-related-work section extended with the new
  clusters; `docs/point_in_time.md` added.
- **Verified abstracts**: `docs/results/arxiv_abstracts_2026_11.json` stores the
  title, authors, date and abstract for 16 key papers; six also have a
  PaperDaily detail record with DOI. This replaces the earlier snippet-only
  notes for the core citations.

## What to do next

**P0 — paper credibility**

1. Add a **production point-in-time feed**: E11 is a contract, not a vintage
   archive. The benchmark's claim is mechanism-level directional skill, not a
   deployable signal.
2. Add **FCM and RICE-Alpha** to the paper's closest-work paragraph and explain
   the difference in one sentence each. (Done in the outline; authors and
   abstracts verified for both.)
3. Add **FinVerify / NumTrace** to the verification paragraph; state that Domino
   verifies transmission signs, not answers or filings. (Done; abstracts and
   authors verified.)

**P1 — stronger system**

4. Extend P-013 to **period/entity/scope** (E12): each memo number should carry
   a reference to the structured field (value, unit, period, entity), not just a
   dimensional check. This is the NumTrace agenda applied to our memo.
5. Consider an **FCM baseline** on the curated benchmark. It would test whether
   a learned weighted graph beats our qualitative mechanism graph — a useful
   adversarial baseline, not a required one.
6. Extend the audit ledger toward **FAAB-style attribution**: when a memo fails,
   name the earliest responsible stage (extraction, retrieval, transmission,
   narration), not just the failed policy. The ledger already stores the trace;
   the attribution layer is missing.

**P2 — paper experiments**

6. **E10 monetary/information decomposition** remains the scientifically
   strongest extension, but needs intraday rate-equity data.
7. Optional **E8 LLM perception** to make the neuro-symbolic claim concrete
   rather than architectural.

## Uncertainties

- Abstracts were verified for the 16 key papers; full PDFs were not read, so
  method details beyond the abstract are still open. The JSON artifact is the
  evidence for what was verified.
- VA-NSF was only seen through a Chinese summary; its venue, authors and exact
  title still need verification.
- `ADAM` is an early GitHub project (secondary report: ~4 stars); treat it as a
  positioning signal, not a peer-reviewed baseline.
- FAAB and XNSTL were verified through PaperDaily detail records (DOI and
  abstract), but their full texts were not read.
- Some non-arXiv dates are search-index dates; the DOI/arXiv identifiers are the
  stable keys.

## Search log (selected)

Queries included: `neuro-symbolic finance`, `Online-Adaptive Fuzzy Cognitive
Maps`, `VA-NSF 神经符号 互联网金融`, `FinVerify financial agents`, `NumTrace
number provenance`, `RICE-Alpha event graphs`, `Structured Event Representation
stock returns`, `Detecting Lookahead Bias LLM Forecasts`, `Temporal Leakage LLM
Backtesting`, `Fin-RATE SEC filings`, `FOMC 文本 大模型 资产`, `事件研究
大语言模型`, `SMT 金融 形式化 验证`, `金融 合规 大模型 约束 验证`.

PaperDaily recovered during the same day and was rerun with
`neuro-symbolic financial forecasting`, `fuzzy cognitive maps financial`,
`financial agent verification` and `number provenance financial analyst`. Those
queries surfaced FAAB, XNSTL and the LLM-assisted FCM paper. The 16 arXiv
abstracts were then fetched directly from `arxiv.org/abs/<id>` and stored in
`docs/results/arxiv_abstracts_2026_11.json`. Full PDF reading remains the next
step for method-level replication, not for the positioning claims above.
