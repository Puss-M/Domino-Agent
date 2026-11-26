# Paper outline

Working title:

> **Neuro-Symbolic Macro Transmission: Sign-Verified Influence Graphs, a 92-Event Benchmark, and a Documented Failure Boundary**

Target venues, in order:

1. **ICAIF** (ACM International Conference on AI in Finance) — main track. Best fit for a system + benchmark + negative-result paper.
2. **NeurIPS workshop** on foundation models for economics/finance (or the AI for Science workshop) — faster feedback, shorter format.
3. **Journal of Financial Data Science / Digital Finance** — extended version with the high-frequency surprise experiment.

## Abstract (draft)

> Macro event analysis with LLMs usually stops at prompt orchestration: an LLM proposes a causal chain and another LLM reviews it. We argue that this architecture has a structural verification problem, and build a neuro-symbolic alternative. A cited mechanism library is compiled into a signed influence graph; qualitative sign algebra and an SMT solver certify (or refute) each asset direction, returning a minimal proof core and treating ambiguity as a first-class output. A policy-as-code layer enforces numeric grounding, no-advice language, abstention, and a hash-chained audit trail. An ablation shows the symbolic layer does **not** improve directional accuracy (blend ΔBrier −0.0002, p=0.52); its value is ambiguity disclosure and auditability. A machine-readable point-in-time contract labels every benchmark as **not** a vintage reconstruction, separating parametric lookahead from data-revision leakage. We release a 92-event benchmark (50 curated macro events + 58 systematic FOMC decisions, deduplicated to 92) with paired event-clustered Brier tests. On the curated benchmark the calibrated stack reaches 60.4% directional accuracy (Brier 0.238, AUC 0.634, 95% CI 0.537–0.668), but the improvement over a base rate is not statistically significant. On the systematic FOMC benchmark the mechanism prior is **significantly worse** than a base rate (41.1% vs 56.6%, ΔBrier +0.134, 95% CI 0.076–0.180). A lexicon tone-delta proxy does not rescue it. Even joining the events with the Bu-Rogers-Wu (2021) daily surprise series leaves the mechanism below the base rate (45.3% vs 52.7%; tightening surprises 52.2%, easing surprises 43.3%), consistent with the information effect: a dovish surprise can be bad news. The missing input is not a surprise number but a monetary/information/supply decomposition. We conclude that action-only policy events require high-frequency surprise/positioning data, not better prompt engineering, and that symbolic verification is the right place to put the reliability budget.

## Contributions

1. **Formalization.** Macro transmission as a signed influence digraph with qualitative algebra; an SMT encoding that returns minimal proof cores; ambiguity as a first-class output rather than a confidence score. (Novel combination; closest work is FormaFin/SOVER for SMT verification of financial rules, and Three-Engine for the architecture.)
2. **Benchmark.** DMB: 50 curated macro events, 58 systematic FOMC target-range changes generated from official statements (2004–2025), a 45-event surprise-aware subset joined with the Bu–Rogers–Wu (2021) series, and a 92-event deduplicated mixed set; paired event-clustered Brier tests, calibration, coverage, a Kolari–Pynnönen cross-correlation adjustment, and a documented negative result.
3. **Architecture.** A three-engine neuro-symbolic pipeline: LLM perception (optional) → deterministic sign/transmission engine → policy-gated output with a hash-chained audit ledger.
4. **Negative results.** Action-only FOMC asset direction is not predictable from free daily data; a lexicon tone-delta proxy fails; a published daily surprise series (BRW 2021) still fails (45.3% vs 52.7%, with easing surprises at 43.3%). The missing input is a three-way monetary/information/supply decomposition, not just a surprise number. This is a benchmark finding, not a footnote.

## Related work (with the citations we actually verified)

**The gap (our positioning)**

A 2026 literature sweep across arXiv, PaperDaily, and the major finance venues found **no paper that combines** (a) LLM-extracted signed influence structures over macro variables, (b) a solver-verified sign-consistency layer, and (c) macro transmission evaluation. A follow-up sweep on 2026-11-26 found closer neighbors (FCM forecasting, event-graph stock scoring, financial-agent verification, temporal-leakage benchmarks), but still no system that joins all three. The components exist separately:

- **TraceMAS** (arXiv 2608.03339): traceable multi-agent forecasting with an "Ideal CLD" and a "Data-Grounded CLD"; signed causal-loop diagrams as an inspectable intermediate representation, but no solver verification.
- **AI Economist Agent** (arXiv 2606.20041): LLM agents constrained to registered quantitative models and statistical tests.
- **FinCARE** (arXiv 2510.20221): SEC 10-K knowledge-graph constraints guiding causal discovery; micro, not macro transmission.
- **MechReasoner** (arXiv 2609.34636): a confluence/sign-algebra qualitative simulator and benchmark; shows frontier LLMs collapse as mechanistic complexity rises — motivation for moving the sign algebra into a solver.
- **D2D** (arXiv 2508.05659): compiles causal loop diagrams into executable system-dynamics models; no LLM or verification.
- **VeriFin** (arXiv 2608.10213): grounds LLM financial claims in XBRL facts and checks arithmetic with Z3; 100% observed precision among accepted answers.
- **VeNRA** (arXiv 2603.04663): typed fact ledger + deterministic executor for financial reasoning.
- **VerifiQuant** (arXiv 2611.26649): executable diagnostic contracts so a financial workflow must ground a number, clarify, or refuse.
- **Solver-Aided Policy Compliance** (arXiv 2603.20449): compiles tool-use policies to SMT and intercepts planned calls with runtime Z3 checks.
- **Logic-LM** (EMNLP 2023 Findings) and **LLM-Modulo** (ICML 2024): the canonical "LLM proposes, external verifier disposes" design pattern.

Our contribution is the intersection: a signed macro transmission graph, LLM-perceived events, Z3 proof cores, ambiguity as a first-class output, and a policy-as-code compliance layer — evaluated on a public macro benchmark.

**Closest 2026-11 neighbors (follow-up sweep)**

- **Fuzzy cognitive maps (FCMs).** *Online-Adaptive Fuzzy Cognitive Maps for Neuro-symbolic Financial Forecasting* (arXiv 2611.13388, 2026-11-10; ICMLA 2026, DOI 10.1109/ICMLA69890.2026.00220; Brandon Rodriguez, Abel Deulofeu, Olaoluwa Adigun) pairs an online-adaptive FCM with an LSTM for regime-shifting financial series; the FCM is built from dual-source prices and macro indicators, its edges adapt online via an error-driven Hebbian rule, and an Asymmetric Additive Residual Fusion combines the two signals. The same group builds FCMs from LLM-extracted causal feedback (*The Agentic Leash*, arXiv 2601.00097; *Causal Autoencoder-like Generation of Feedback FCMs with an LLM Agent*, arXiv 2509.25593), and a 2026 methods paper uses multiple LLMs as domain experts to elicit, correct and weight FCM concepts (DOI 10.5281/zenodo.20724740). This is the closest symbolic-graph line: interpretable causal edges with learned weights and dynamics, but no solver-certified sign consistency or ambiguity output. Our graph is a qualitative FCM with proof cores.
- **Event graphs for stock scoring.** *RICE-Alpha* (arXiv 2609.34004, 2026-09-27; Tong Liu, Lanmiao Liu, Xiang Hu) is a point-in-time stock-scoring framework that models issuer chronology, information availability and transition reliability, separating a history-aware multi-agent component from event-graph correction. *Structured Event Representation and Stock Return Predictability* (arXiv 2512.19484, 2025-12-22; Gang Li, Dandan Qiao, Mingxuan Zheng) finds LLM-extracted event features predict cross-sectional returns. These validate the event-driven premise but forecast cross-sectional scores, not macro transmission signs with a formal audit.
- **Financial-agent verification.** *FinVerify* (arXiv 2611.20423, 2026-11-16; Mao Guan, Qian Chen, Ge Meng, Xiao-Yang Liu) analyzes 190 incorrect trajectories and defines five error categories — temporal integrity, source fidelity, comparability, accounting integrity, financial-model fidelity — operationalized as deterministic validation protocols. *NumTrace* (arXiv 2610.34887, 2026-10-26; Tianlei Zhu, Matt White, Xue Liu, Xiao-Yang Liu) is a 540-question, 2,163-document benchmark that audits number provenance (entity, concept, period, unit, scope). *GURU* (arXiv 2611.01001, 2026-10-31) partitions authority so learned models propose and a symbolic rules engine checks consequential actions. *NSVIF* (arXiv 2601.17789) verifies instruction following. *FAAB* (DOI 10.1145/3858063.3858684, 2026-11-14) audits 300 point-in-time financial multi-agent workflows plus 700 single-point interventions, localizing the earliest responsible agent/step. *XNSTL* (DOI 10.36347/sjet.2026.v14i11.001, 2026-11-07) is a broad LLM + symbolic-rule trust layer for banking. These verify answers, numbers, actions or workflow traces; we verify transmission signs and return a minimal proof core. FAAB is the natural next extension of our ledger: attribution, not just detection.
- **Temporal integrity.** *Detecting Lookahead Bias in LLM Forecasts* (arXiv 2512.23847, 2025-12-29; Zhenyu Gao, Wenxi Jiang, Yutong Yan), *Temporal Leakage in LLM Backtesting* (arXiv 2608.02985, 2026-08-04; Zeyu Zhang, Bradly C. Stadie), *FinCutBench* (arXiv 2611.11588, 2026-11-08), *When Does Post-Call Begin?* (arXiv 2610.21659, 2026-10-15) and *LLMs Don't Know What They Know* (arXiv 2611.06808, 2026-11-04) make parametric lookahead a first-class benchmark problem. Our offline path has no LLM in the metric path, which removes parametric leakage by construction; the remaining exposure is revised market data, discussed in Threats.
- **Financial-agent benchmarks.** *Fin-RATE* (arXiv 2602.07294, 2026-02; SEC filings), *FinFIRST* (arXiv 2609.25192), *FinHopper* (arXiv 2610.26036), *AgenticFinBench* (arXiv 2611.04813) and *FinAutoRubric* (arXiv 2609.35744) evaluate QA, retrieval, multi-hop and rubric following. DMB is complementary: its unit is a macro event and a realised asset return, not a question-answer pair.

**Neuro-symbolic verification**
- FormaFin, *Verifiable Financial Analysis with Solver-Guided Reinforcement Learning*, arXiv 2611.28881 (2026-11-24). Trains small models to translate financial rules into SMT formulas; solver computes rewards.
- SOVER, *Formal Certification of Optimization Reformulations via LLM-Assisted SMT Verification*, arXiv 2609.00728 (2026-09-02). Separates semantic mapping from formal certification; Z3 + dReal.
- *Logically Consistent Language Models via Neuro-Symbolic Integration*, 2024. External facts/rules as a consistency loss.
- *Neuro-Symbolic AI: Towards Improving the Reasoning Abilities of LLMs*, 2025 (survey).

**Multi-agent reliability**
- *More Debate, Same Evidence: Structural Limits of Homogeneous Multi-Agent Groundedness*, arXiv 2608.00243 (2026-08-04). Debate changes groundedness by +8.5 to −4.4pp; three of six benchmarks inconclusive.
- *The Hallucination Snowball*, arXiv 2608.14588 (2026-08-18). Raw fact → derived → narrative → invisible; escape probabilities 24.6%/48.3%/89.3%.
- *Delayed Verification Destabilizes Multi-Agent LLM Belief*, arXiv 2606.27409 (2026-06-29). Verification delay and corrector placement.
- *Mitigating Hallucinations in Finance-Based Multi-Agent LLM Systems*, Electronics 2026. Six signals: entailment, semantic similarity, claim verification, numeric consistency, token overlap, confidence calibration; 78.4% fix rate on FinQA hallucinations.

**Architecture**
- *Beyond LLM Wrappers: Context Engineering and the Three-Engine Architecture for Reliable Financial AI*, arXiv 2610.39230 (2026-10-30). Financial knowledge graph + deterministic compute + multi-agent LLM layer.
- FinRobot (AI4Finance) — deterministic compute, LLM narration, provenance.
- TradingAgents (TauricResearch) — role-separated agents; used as the baseline "multi-agent debate" architecture.

**FOMC text and surprises**
- Bu, Rogers & Wu, *A unified measure of Fed monetary policy shocks*, JME 118:331–349 (2021). The daily shock series used in the surprise-aware benchmark.
- Jarociński & Karadi, *Deconstructing Monetary Policy Surprises: The Role of Information Shocks*, AEJ:Macro 12(1) (2020). Monetary vs information shock decomposition.
- *Supply-Side Information and Monetary Policy Surprises*, SSRN 7633199 (2026-10-20), DOI 10.2139/ssrn.7633199. Supply conditions enter high-frequency surprises through rate–exchange-rate comovement; motivates a three-way decomposition.
- Schmeling & Wagner, *Does Central Bank Tone Move Asset Prices?*, JFQA 60:36–67 (2024). Tone changes move asset prices beyond policy actions.
- Doh, Song & Yang, *Deciphering Federal Reserve Communication via Text Analysis of Alternative FOMC Statements*, AEJ:Macro 18(3) (2026). Text stance decomposed into expected/surprise.
- Tang & Yang, *Mind the Shift: Decoding Monetary Policy Stance from FOMC Statements with LLMs*, arXiv 2603.14313 (2026). Delta-consistent tone scoring.
- Acosta, Ajello, Bauer, Loria & Miranda-Agrippino, *Financial Market Effects of FOMC Communication*, FRBSF WP 2025-30 / SSRN 5944756. USMPD public event-study database.
- Bauer & Swanson, *A Reassessment of Monetary Policy Surprises and High-Frequency Identification*, NBER Macroeconomics Annual 2023 (364 citations).
- Nakamura & Steinsson, *High Frequency Identification of Monetary Non-Neutrality: The Information Effect*, QJE 2013 (691 citations).
- *Changing the Narrative: Macro-Financial Federal Reserve Communication Shocks*, SSRN 6677954 (2026-04-29). Belief objects and narrative-baseline departure.
- *Identifying Monetary Policy Shocks with Large Language Models*, SSRN 7560498 (2026-10-05). Pre-FOMC briefing materials.
- *AI Listening to Central Banks*, SSRN 6949226 (2026-06-16).

**Event-study method**
- Kolari & Pynnönen, *Event Study Testing with Cross-sectional Correlation of Abnormal Returns*, RFS 2010 (615 citations). Cross-correlation-adjusted BMP statistic.
- MacKinlay (1997), event-study foundations.

**Causal discovery with LLMs**
- *Efficient Causal Graph Discovery Using Large Language Models*, arXiv 2402.01207 (BFS, linear queries, SOTA on real graphs).
- *Large Language Models for Constrained-Based Causal Discovery*, 2024 (LLM answers conditional-independence queries for PC).
- *CauTion: Knowing When to Trust LLMs for Ensemble Causal Discovery*, arXiv 2606.03602.
- Kıcıman, Ness, Sharma & Tan, *Causal Reasoning and Large Language Models: Opening a New Frontier for Causality*, TMLR 2024 (arXiv 2305.00050).
- *Scaling Point-in-Time Language Models*, arXiv 2607.11889 — temporal filtering to eliminate lookahead bias.
- *Ideological Bias in LLMs' Economic Causal Reasoning*, arXiv 2604.21334 — a warning for LLM-perceived macro causal structure.

## Method

1. **Perception.** Rule-first extraction (numbers, units, surprise, entities, sentiment, dedupe); optional LLM with schema-constrained output, never allowed to write numeric fields.
2. **Retrieval.** Cited mechanism library (20 mechanisms, 14 channels); actor/condition filtering; abstain when no match.
3. **Symbolic kernel.** Signed influence graph; qualitative path composition; Z3 proof cores; ambiguity output; typed units.
4. **Numeric transmission.** Channel/loading aggregation; expected CAR prior; audit.
5. **Compliance.** Policy-as-code P-001–P-013; hash-chained ledger.
6. **Evaluation.** Event study (market model, CAR[0,+1], event-day alignment), Kolari–Pynnönen cross-correlation adjustment, walk-forward stack (mechanism/analog/base), Platt calibration, paired event-clustered Brier tests, coverage.

## Experiments

| # | Experiment | Status | Expected figure/table |
|---|---|---|---|
| E1 | Curated benchmark: mechanism/analog/hybrid/stack/calibrated vs base | done | Table 1 (60.4%, 0.238, 0.634) |
| E2 | System FOMC benchmark (58 events) | done | Table 2 (41.1% vs 56.6%, ΔBrier +0.134) |
| E3 | Tone-delta surprise proxy | done (negative) | Table 3 (44–50%, base 52.6%) |
| E4 | Symbolic proof coverage / ambiguity | done | Table 4 (66.7% coverage on hawkish hike; TLT/GLD ambiguous) |
| E5 | Hallucination injection: 10 clean memos × 6 corruption types | done | Table 5 (60/60 detected; 0/10 clean false positives) |
| E6 | Ablation: numeric-only vs symbolic-only vs gated vs blend | done (negative) | Table 7 (no predictive lift; coverage falls to 62.5%/56.7%) |
| E7 | Kolari–Pynnönen cross-correlation-adjusted CAR test | done | Table 6 (rho 0.04–0.06; FOMC sig. events 6.9% → 3.5%) |
| E8 | LLM perception vs rule extraction (optional) | todo, needs API key | Extraction accuracy / cost |
| E9 | Surprise-aware FOMC with BRW (2021) daily shocks | done (negative) | Table 3b (45.3% vs 52.7%; easing 43.3%) |
| E10 | Monetary / information / supply shock decomposition (Jarociński–Karadi 2020; SSRN 7633199) | todo | FOMC accuracy/Brier after decomposition; needs intraday rate, equity and FX co-movement |
| E11 | Point-in-time contract and lookahead audit | done | Table 8 (all benchmarks `not_point_in_time`; dataset-specific culprits) |
| E12 | Period/entity/scope provenance (NumTrace agenda) | partial (P-013 units done) | Provenance failure taxonomy; 60/60 unit injections |

## Results to report now

- Curated: 60.4% accuracy, Brier 0.238, AUC 0.634, coverage 96.4%, 95% CI 0.537–0.668; vs base ΔBrier −0.0082 (CI −0.0235–0.0055, p=0.128, not significant); vs mechanism ΔBrier −0.0212 (p=0.048).
- FOMC: mechanism 41.1%, Brier 0.384; base 56.6%, Brier 0.250; ΔBrier +0.134 (CI 0.076–0.180).
- 5-day curated: 54.5%, Brier 0.252, AUC 0.528.
- Surprise-aware FOMC (BRW 2021, 45 events): 45.3% vs base 52.7%; tightening 52.2%, easing 43.3%.
- Symbolic: 19 nodes/78 edges/acyclic for a hawkish shock; 8 proved, 4 ambiguous; proof core for QQQ = {MON_TIGHTEN}.
- Policy injection (E5): 60/60 injected corruptions detected across fake numbers, advice, fake mechanism IDs, fake citations, out-of-universe assets and right-number/wrong-unit claims; 0/10 clean memos raised an error policy.
- Symbolic ablation (E6): numeric-only 61.4% / Brier 0.259 on curated; symbolic-only 60.5% on 62.5% coverage; gated 60.5% on 62.5%; blend 61.4% / 0.258. Blend vs numeric ΔBrier −0.0002 (95% CI −0.0073–0.0072, p=0.52). FOMC: 41.1% numeric, 41.4% symbolic on 56.7% coverage; blend ΔBrier +0.0025 (95% CI −0.0013–0.0067, p=0.89). Curated 5-day, surprise-aware and extended show the same non-significant pattern. **No predictive lift** — the symbolic layer's value is auditability and structured ambiguity.
- Point-in-time audit (E11): every benchmark is `not_point_in_time`; culprits are Yahoo adjusted prices, editorial labels, the FOMC compilation and the ex-post BRW series. The LLM-free metric path removes parametric lookahead but not data-revision leakage.
- Cross-sectional correlation (E7): mean residual rho 0.043–0.059; KP inflation 1.19–1.23. Mean |BMP| falls from 1.18–1.29 to 1.01–1.06. FOMC significant-event share falls 6.9% → 3.5% (surprise-aware 8.9% → 4.4%). Pooled equal-weighted CAR: curated t 1.92 → 1.65, FOMC 0.25 → 0.21, surprise-aware −0.38 → −0.33, extended 1.35 → 1.14. No pooled CAR is significant.

## Threats to validity

- 50 curated events and 58 FOMC events; wide intervals.
- Curated labels are editorial; extraction accuracy is in-sample vocabulary coverage.
- FOMC headlines are templated; extraction metrics exclude them.
- Yahoo adjusted closes are not point-in-time. The offline path has no LLM in the metric path, so it avoids the parametric lookahead documented by Gao et al. (2512.23847) and Zhang & Stadie (2608.02985); it does not avoid revised-price leakage. E11 is the missing audit.
- Mechanism library is authored, not preregistered.
- Symbolic proofs are relative to the library; they do not establish real-world causality.
- Tone-delta is a lexicon proxy; a belief-object or LLM-based measure might do better (Changing the Narrative).
- The event-study cross-section is only 11 assets (SPY excluded), so the KP adjustment has limited power; residual correlation is estimated over a 100-day window and treated as constant.
- Per-asset CAR t-statistics are not multiple-testing adjusted; they are descriptive.

## What is missing for a strong submission

1. **Period/entity/scope provenance** (E12) — extend P-013 beyond units, following NumTrace (2610.34887): each memo number should reference the structured field's entity, concept, period and scope.
2. **Optional LLM perception** (E8) — one open model or API, schema-constrained, with the rule extractor as fallback. Report extraction accuracy and cost. This makes the "neuro-symbolic" claim concrete rather than architectural.
3. **Monetary/information/supply decomposition** (E10) — the BRW surprise test shows a surprise number is not enough; use Jarociński–Karadi (2020) plus the 2026 supply-side rate–FX comovement result (SSRN 7633199). If intraday data are unavailable, the negative result stands as a benchmark contribution.
4. **A production point-in-time feed** — E11 is a contract, not a vintage archive. A deployable system needs as-traded prices and a real-time surprise feed; the current benchmark's claim is mechanism-level directional skill, not a trading signal.
5. **A cleaner related-work positioning** — FinVerify verifies answers, NumTrace verifies number provenance, GURU verifies actions; we verify transmission signs and expose ambiguity. FCM/RICE-Alpha build event graphs; we add solver proof cores and a public negative result. No single neighbor does both.

## Suggested timeline

- Week 1: E10 (shock decomposition), optional E8, E12 (period/entity provenance).
- Week 2: paper draft (8 pages), figures from `docs/results/`, artifact appendix.
- Week 3: internal review, reproduction from a clean clone, submission.
- Optional parallel: high-frequency surprise adapter; if it works, promote E9 to a main result.
