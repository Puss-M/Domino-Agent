# Model card: Domino Agent v0.4

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
| FOMC 58 (stress) | Stacked + Platt | 0.412 | 0.255 | 0.404 | 93.1% |
| Extended 92 | Stacked + Platt | 0.508 | 0.248 | 0.578 | 96.3% |

The FOMC mechanism-only model is **significantly worse** than the always-up base rate (ΔBrier +0.1338, 95% CI 0.076–0.180). This is the model's most important limitation.

## Failure modes

1. **Action-only policy events.** Without a surprise/positioning measure, the mechanism sign is wrong across regimes (normalization vs recession vs inflation shock).
2. **Duration-sensitive equities.** QQQ and XLU are over-predicted down around hikes.
3. **China policy.** Two events; stimulus transmission is regime-dependent.
4. **Geopolitics.** The 1-day equity sign is noisy even when the safe-haven direction is right.
5. **Five-day horizon.** The announcement-session edge decays; 5-day accuracy is 54.5%, AUC 0.528.
6. **Middle-bin calibration.** Noisy with 33 predictions per bin and correlated assets within events.
7. **Symbolic ambiguity.** TLT/IEF/GLD/XLU are genuinely ambiguous under a hawkish shock (yield vs safe-haven paths). The system reports `?`; it does not resolve it without a regime condition or data.
8. **Proofs are relative.** A Z3 proof core means the cited mechanisms entail the direction; it does not mean the mechanisms are true or that the effect is causal.

## Symbolic verification and compliance

- The matched mechanisms compile to a signed influence graph; Z3 returns a minimal proof core or an ambiguity status per asset.
- Policies P-001–P-009 enforce disclaimer, no-advice, evidence citations, numeric grounding, abstention, audit pass, surprise warnings and proof consistency.
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
