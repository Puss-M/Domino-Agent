# Paper outline

Working title:

> **Neuro-Symbolic Macro Transmission: Sign-Verified Influence Graphs, a 92-Event Benchmark, and a Documented Failure Boundary**

Target venues, in order:

1. **ICAIF** (ACM International Conference on AI in Finance) — main track. Best fit for a system + benchmark + negative-result paper.
2. **NeurIPS workshop** on foundation models for economics/finance (or the AI for Science workshop) — faster feedback, shorter format.
3. **Journal of Financial Data Science / Digital Finance** — extended version with the high-frequency surprise experiment.

## Abstract (draft)

> Macro event analysis with LLMs usually stops at prompt orchestration: an LLM proposes a causal chain and another LLM reviews it. We argue that this architecture has a structural verification problem, and build a neuro-symbolic alternative. A cited mechanism library is compiled into a signed influence graph; qualitative sign algebra and an SMT solver certify (or refute) each asset direction, returning a minimal proof core and treating ambiguity as a first-class output. A policy-as-code layer enforces numeric grounding, no-advice language, abstention, and a hash-chained audit trail. We release a 92-event benchmark (50 curated macro events + 58 systematic FOMC decisions, deduplicated to 92) with paired event-clustered Brier tests. On the curated benchmark the calibrated stack reaches 60.4% directional accuracy (Brier 0.238, AUC 0.634, 95% CI 0.537–0.668), but the improvement over a base rate is not statistically significant. On the systematic FOMC benchmark the mechanism prior is **significantly worse** than a base rate (41.1% vs 56.6%, ΔBrier +0.134, 95% CI 0.076–0.180). A lexicon tone-delta proxy does not rescue it. We conclude that action-only policy events require high-frequency surprise/positioning data, not better prompt engineering, and that symbolic verification is the right place to put the reliability budget.

## Contributions

1. **Formalization.** Macro transmission as a signed influence digraph with qualitative algebra; an SMT encoding that returns minimal proof cores; ambiguity as a first-class output rather than a confidence score. (Novel combination; closest work is FormaFin/SOVER for SMT verification of financial rules, and Three-Engine for the architecture.)
2. **Benchmark.** DMB: 50 curated macro events, 58 systematic FOMC target-range changes generated from official statements (2004–2025), and a 92-event deduplicated mixed set; paired event-clustered Brier tests, calibration, coverage, and a documented negative result.
3. **Architecture.** A three-engine neuro-symbolic pipeline: LLM perception (optional) → deterministic sign/transmission engine → policy-gated output with a hash-chained audit ledger.
4. **Negative result.** Action-only FOMC asset direction is not predictable from free daily data; a lexicon tone-delta proxy fails; the missing input is high-frequency surprise. This is a benchmark finding, not a footnote.

## Related work (with the citations we actually verified)

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

## Method

1. **Perception.** Rule-first extraction (numbers, units, surprise, entities, sentiment, dedupe); optional LLM with schema-constrained output, never allowed to write numeric fields.
2. **Retrieval.** Cited mechanism library (20 mechanisms, 14 channels); actor/condition filtering; abstain when no match.
3. **Symbolic kernel.** Signed influence graph; qualitative path composition; Z3 proof cores; ambiguity output; typed units.
4. **Numeric transmission.** Channel/loading aggregation; expected CAR prior; audit.
5. **Compliance.** Policy-as-code P-001–P-009; hash-chained ledger.
6. **Evaluation.** Event study (market model, CAR[0,+1], event-day alignment), walk-forward stack (mechanism/analog/base), Platt calibration, paired event-clustered Brier tests, coverage.

## Experiments

| # | Experiment | Status | Expected figure/table |
|---|---|---|---|
| E1 | Curated benchmark: mechanism/analog/hybrid/stack/calibrated vs base | done | Table 1 (60.4%, 0.238, 0.634) |
| E2 | System FOMC benchmark (58 events) | done | Table 2 (41.1% vs 56.6%, ΔBrier +0.134) |
| E3 | Tone-delta surprise proxy | done (negative) | Table 3 (44–50%, base 52.6%) |
| E4 | Symbolic proof coverage / ambiguity | done | Table 4 (66.7% coverage on hawkish hike; TLT/GLD ambiguous) |
| E5 | Hallucination injection: N memos with fake numbers/advice | partial (1 case) | Detection rate by policy; need N=50–100 |
| E6 | Ablation: numeric-only vs symbolic-only vs both | todo | Ambiguity catch rate; proof coverage |
| E7 | Kolari–Pynnönen cross-correlation-adjusted CAR test | todo | Robustness table |
| E8 | LLM perception vs rule extraction (optional) | todo, needs API key | Extraction accuracy / cost |
| E9 | High-frequency surprise adapter (if data available) | todo | FOMC accuracy/Brier after surprise conditioning |

## Results to report now

- Curated: 60.4% accuracy, Brier 0.238, AUC 0.634, coverage 96.4%, 95% CI 0.537–0.668; vs base ΔBrier −0.0082 (CI −0.0235–0.0055, p=0.128, not significant); vs mechanism ΔBrier −0.0212 (p=0.048).
- FOMC: mechanism 41.1%, Brier 0.384; base 56.6%, Brier 0.250; ΔBrier +0.134 (CI 0.076–0.180).
- 5-day curated: 54.5%, Brier 0.252, AUC 0.528.
- Symbolic: 19 nodes/78 edges/acyclic for a hawkish shock; 8 proved, 4 ambiguous; proof core for QQQ = {MON_TIGHTEN}.
- Policy injection: advice language and three fake numbers detected.

## Threats to validity

- 50 curated events and 58 FOMC events; wide intervals.
- Curated labels are editorial; extraction accuracy is in-sample vocabulary coverage.
- FOMC headlines are templated; extraction metrics exclude them.
- Yahoo adjusted closes are not point-in-time.
- Mechanism library is authored, not preregistered.
- Symbolic proofs are relative to the library; they do not establish real-world causality.
- Tone-delta is a lexicon proxy; a belief-object or LLM-based measure might do better (Changing the Narrative).

## What is missing for a strong submission

1. **Kolari–Pynnönen test** (E7) — a standard event-study robustness check; low effort, high credibility.
2. **Hallucination injection at scale** (E5) — 50–100 injected memos, report detection by policy and false-positive rate on clean memos. This directly supports the "reduce hallucination" claim.
3. **Ablation** (E6) — show that symbolic verification catches ambiguity that the numeric model hides; quantify how often.
4. **Optional LLM perception** (E8) — one open model or API, schema-constrained, with the rule extractor as fallback. Report extraction accuracy and cost. This makes the "neuro-symbolic" claim concrete rather than architectural.
5. **High-frequency surprise** (E9) — even a small vendor sample or a public intraday proxy would turn the FOMC negative result into a positive one. If unavailable, the negative result stands as a benchmark contribution.
6. **A cleaner related-work positioning** — FormaFin verifies rules; we verify transmission signs and expose ambiguity. Three-Engine is an architecture paper; we add a benchmark and a negative result. Neither does both.

## Suggested timeline

- Week 1: E5 (injection at scale), E7 (KP test), E6 (ablation).
- Week 2: paper draft (8 pages), figures from `docs/results/`, artifact appendix.
- Week 3: internal review, reproduction from a clean clone, submission.
- Optional parallel: high-frequency surprise adapter; if it works, promote E9 to a main result.
