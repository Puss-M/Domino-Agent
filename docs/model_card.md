# Model card: Domino Agent v0.6

## Model summary

Domino Agent is an **evidence-gated macro transmission pipeline**, not a single neural network. It combines:

1. a rule-first financial event extractor;
2. a cited mechanism library;
3. a deterministic channel/asset transmission model;
4. an evidence audit with abstention;
5. a walk-forward stack (mechanism, historical analog, base rate) with Platt calibration;
6. a symbolic kernel: sign algebra, Z3 proof cores, ambiguity as a first-class output;
7. a policy-as-code compliance layer with a hash-chained audit ledger.

The offline path is LLM-free. Every number, sign and graph edge is produced by typed code.

## Intended use

- Research and education on macro event transmission and event-study evaluation.
- Hypothesis generation with explicit citations and falsifiers.
- Benchmarking extraction, calibration and selective prediction on small event samples.

## Out-of-scope use

- Live trading, portfolio construction, execution, market impact or capacity.
- Investment advice, regulatory reporting or risk limits.
- Causal identification. A cited transmission channel is a hypothesis, not an identified structural effect.
- Claims of universal alpha. The curated improvement is not statistically significant, and the FOMC stress test is negative.

## Inputs

- A headline and optional summary (English or Chinese), or a dated event from the bundled datasets.
- Optional full FOMC statement text (used only for the systematic benchmark and sentiment analysis).
- Market snapshot for outcomes and analog priors.

## Outputs

- `MacroEvent`: type, direction, actor, magnitude, surprise, entities, sentiment, confidence.
- A two-layer graph: `event → channel → asset`, with mechanism IDs, evidence grades and citations.
- Asset predictions: `p_up`, expected 5-day CAR prior, confidence, evidence grade, abstention/conflict flags.
- A research memo with transmission channels, falsifiers and monitoring indicators.
- An audit report: citation completeness, speculative mechanisms, sign conflicts, look-ahead, coverage.
- A symbolic report: signed influence graph, per-asset proof status (`proved`/`ambiguous`/`not_entailed`/`unverified`), minimal proof cores, policy results, ontology issues, ledger hash.
- Backtest metrics: accuracy, Brier, AUC, ECE, coverage, event-clustered CIs and paired Brier comparisons.

## Training and estimation

- No end-to-end training. The mechanism library is authored from the literature.
- The stack weights and Platt calibration are fitted on the **first half** of each benchmark; the second half is held out.
- Analog priors use only matured prior events.
- The FOMC benchmark uses templated headlines, so extraction metrics exclude it.

## Evaluation

Primary results (1-day window):

| Benchmark | Headline model | Accuracy | Brier | AUC | Coverage |
|---|---|---:|---:|---:|---:|
| Curated 50 | Stacked + Platt | 0.604 | 0.238 | 0.634 | 96.4% |
| FOMC 58 (action-only) | Stacked + Platt | 0.412 | 0.255 | 0.404 | 93.1% |
| FOMC 45 (surprise-aware) | Stacked + Platt | 0.453 | 0.253 | 0.450 | 99.2% |
| Extended 92 | Stacked + Platt | 0.508 | 0.248 | 0.578 | 96.3% |

The FOMC mechanism-only model is **significantly worse** than the always-up base rate (ΔBrier +0.1338, 95% CI 0.076–0.180). This is the model's most important limitation.

The E6 ablation shows the symbolic layer does **not** improve directional accuracy: the symbolic-blend vs numeric-only Brier delta is −0.0002 on curated (p=0.52) and +0.0025 on FOMC (p=0.89). Its value is ambiguity disclosure, proof cores and auditability, not accuracy. The E11 point-in-time audit labels every benchmark `not_point_in_time`; the LLM-free metric path removes parametric lookahead, not revised-data leakage.

## Failure modes

1. **Action-only policy events.** Without a surprise/positioning measure, the mechanism sign is wrong across regimes (normalization vs recession vs inflation shock).
2. **Surprise-aware policy events.** Even the BRW (2021) daily surprise does not fix the sign (45.3% vs base 52.7%); easing surprises are 43.3%. The information effect requires a monetary/information decomposition, not just a surprise number.
3. **Duration-sensitive equities.** QQQ and XLU are over-predicted down around hikes.
4. **China policy.** Two events; stimulus transmission is regime-dependent.
5. **Geopolitics.** The 1-day equity sign is noisy even when the safe-haven direction is right.
6. **Five-day horizon.** The announcement-session edge decays; 5-day accuracy is 54.5%, AUC 0.528.
7. **Middle-bin calibration.** Noisy with 33 predictions per bin and correlated assets within events.
8. **Symbolic ambiguity.** TLT/IEF/GLD/XLU are genuinely ambiguous under a hawkish shock (yield vs safe-haven paths). The system reports `?`; it does not resolve it without a regime condition or data.
9. **Proofs are relative.** A Z3 proof core means the cited mechanisms entail the direction; it does not mean the mechanisms are true or that the effect is causal.
10. **Symbolic layer does not add accuracy.** In E6, symbolic-only covers 62.5% (curated) / 56.7% (FOMC) of predictions at roughly the same accuracy as the numeric model; gating and blending do not improve Brier. Do not use the symbolic layer as a performance claim.
11. **Not point-in-time.** Yahoo adjusted closes, editorial labels, the FOMC compilation and the ex-post BRW series are revised or ex-post; E11 reports the dataset-specific verdict.

## Symbolic verification and compliance

- The matched mechanisms compile to a signed influence graph; Z3 returns a minimal proof core or an ambiguity status per asset.
- Policies P-001–P-013 enforce disclaimer, no-advice, evidence citations, numeric and unit grounding, abstention, audit pass, surprise warnings, proof consistency, and grounding of mechanism IDs, citations and assets.
- Every analysis is committed to a SHA-256 hash-chained ledger (`backend/.cache/audit/ledger.jsonl`); the response carries the record hash.
- Compliance mapping is documented in [`neuro_symbolic.md`](neuro_symbolic.md): SEC Marketing Rule / AI-washing substantiation, Fed SR 11-7 independent validation, MiFID II accountability, EU AI Act logging/human oversight.

## Ethical and regulatory notes

- The system outputs research hypotheses, not recommendations.
- It does not use personal data.
- Data licenses: see [`data_sources.md`](data_sources.md). The Loughran–McDonald dictionary is not redistributed.
- The project should not be used to make suitability, credit, employment or consumer decisions.

## Maintenance

- Refresh the market snapshot with `scripts/fetch_market_snapshot.py`.
- Rebuild the FOMC benchmark with `scripts/build_fomc_events.py`.
- Re-run the backtest and update `docs/results/` and `docs/evaluation.md` when data or mechanisms change.
- Do not tune on the held-out half. If you change the mechanism library after seeing test results, report the new benchmark as a new version.

## Citation

If you use the benchmark, cite the repository and the upstream FOMC dataset:

```
Puss-M. Domino Agent: Event-driven macro transmission with cited mechanisms.
https://github.com/Puss-M/Domino-Agent
```

```
HusseinKh90. FOMC Dataset: Federal Reserve Statements, Minutes and Transcripts.
https://github.com/HusseinKh90/fomc-dataset
```
