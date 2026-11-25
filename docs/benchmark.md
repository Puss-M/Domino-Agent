# Benchmark card: Domino Macro Bench (DMB)

## What it is

DMB is a small, reproducible event-study benchmark for testing whether a signed macro-transmission hypothesis matches the first trading session's abnormal returns. It is designed to test **evidence and calibration**, not to crown a trading strategy.

## Datasets

| Split | Events | Period | Construction | Role |
|---|---:|---|---|---|
| `curated` | 50 | 2018-03 – 2025-04 | Hand-curated headlines and editorial type/direction labels | Primary text + transmission benchmark |
| `fomc` | 58 | 2004-06 – 2025-12 | Generated from official FOMC statements; only non-zero target-range changes | Homogeneous action-only stress test |
| `fomc_surprise` | 45 | 2004-06 – 2025-12 | Same events joined with Bu-Rogers-Wu (2021) daily surprises; direction = surprise sign; \|surprise\| ≥ 2bp | Surprise-aware information-effect test |
| `extended` | 92 | 2004-06 – 2025-12 | Curated + FOMC, deduplicated by `(event_type, date)` | Mixed-family robustness check |

### Curated split

- 50 events across monetary policy, inflation, trade policy, energy supply, geopolitics, financial stability, China policy, fiscal policy and labour market.
- Headlines and summaries are real-ish text; labels are editorial and based on the official action plus published consensus, not the market reaction.
- Source URLs point to the Federal Reserve, BLS, USTR, White House, OPEC, FDIC or a wire service.

### FOMC split

- Official statements from the public [FOMC Dataset](https://github.com/HusseinKh90/fomc-dataset), subset 2000–2025.
- The parser reads the target range from the statement text, computes the change versus the previous statement, and emits only non-zero changes.
- 2000–2003 statements are excluded because their single-value phrasing produced parsing artefacts.
- Headlines are templated (`Fed raises rates by 25 basis points to 1.25%`); the summary is a statement excerpt.
- Surprise is `neutral`: no Fed-funds/SOFR futures or consensus series is bundled. This is the benchmark's central limitation and the reason it is a stress test.
- The build is reproducible: `python scripts/build_fomc_events.py`.

### Extended split

Curated + FOMC, deduplicated by event type and date. Curated events win when both describe the same decision. This split is reported for completeness; it is not the headline because the two families have different information content.

## Outcomes

- 12 ETFs: SPY, QQQ, TLT, IEF, UUP, GLD, XLE, XLU, EEM, HYG, ^VIX, FXI.
- Daily adjusted close from Yahoo Finance (2000–present snapshot).
- Market model estimated on `[-120, -21]`; CAR over `[0, +1]` trading days.
- Event-day alignment: before-open/during → same session; after-close/non-trading → next session.
- Flat threshold: 10bp (100bp for ^VIX); flat outcomes are excluded from directional accuracy.

## Splits and leakage controls

- First 50% of events by date are used to fit stack weights and Platt calibration; the last 50% is held out.
- Analog priors use only events whose outcome window has fully matured before the current event day.
- Bootstrap resamples events, not asset rows; paired Brier comparisons use the same event clusters.
- The mechanism library is fixed before evaluation; it is not fitted to the test outcomes.
- The FOMC headlines are generated from the target range, so extraction metrics exclude them (`extraction.n = 0`).

## Leaderboard (1-day window)

### Curated (50 events, 265 held-out predictions)

| Model | Coverage | Accuracy | Brier | AUC | ECE |
|---|---:|---:|---:|---:|---:|
| Always-up base rate | 100% | 0.538 | 0.244 | 0.561 | 0.086 |
| Mechanism only | 92.4% | 0.614 | 0.259 | 0.613 | 0.117 |
| Analog only | 69.8% | 0.586 | 0.248 | 0.581 | 0.112 |
| Stacked + Platt | 96.4% | 0.604 | 0.238 | 0.634 | 0.052 |

### FOMC stress test (58 events, 297 held-out predictions)

| Model | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|
| Always-up base rate | 100% | **0.566** | 0.250 | 0.544 |
| Mechanism only | 93.1% | **0.411** | 0.384 | 0.416 |
| Analog only | 93.1% | 0.524 | 0.262 | 0.506 |
| Stacked + Platt | 93.1% | 0.412 | 0.255 | 0.404 |

Mechanism vs base rate: ΔBrier **+0.1338**, 95% CI **[0.076, 0.180]**, one-sided p=**1.0**. The mechanism prior is significantly worse than a naive base rate on action-only policy events.

### Extended (92 events, 490 held-out predictions)

| Model | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|
| Always-up base rate | 100% | 0.541 | 0.253 | 0.536 |
| Mechanism only | 93.3% | 0.575 | 0.283 | 0.562 |
| Analog only | 66.0% | 0.564 | 0.258 | 0.551 |
| Stacked + Platt | 96.3% | 0.508 | 0.248 | 0.578 |

## Symbolic verification on the benchmark

For the hawkish-hike example, the matched mechanisms compile to a 19-node / 78-edge signed influence graph. 8 of 12 assets are formally proved, 4 are ambiguous (TLT, IEF, GLD, XLU) because the yield and safe-haven paths conflict. Proof coverage is 66.7% on the hike example and 81.8% on the CPI/China examples.

The symbolic layer is not part of the accuracy metrics: it does not change `p_up`. It is a separate, auditable statement about **whether the direction is entailed by the cited mechanisms**. A proof is relative to the library; it is not a causal identification result.

## Intended use

- Test whether a cited transmission mechanism has directional skill on a small event sample.
- Compare calibration, coverage and abstention behavior across event families.
- Teach event-study alignment, market-model CARs, walk-forward validation and paired bootstrap comparisons.

## Out of scope

- Trading, portfolio construction, execution, capacity or transaction costs.
- Causal identification (no counterfactual, no instrument, no identification strategy).
- Regulatory or investment advice.
- Claims about live performance. The prices are revised adjusted closes, not point-in-time data.

## Known limitations

1. **Small samples.** 50 curated and 58 FOMC events; the confidence intervals are wide.
2. **No surprise series.** The FOMC benchmark tests the action, not the surprise. This is why it fails.
3. **Curated labels.** The 50-event labels are editorial; extraction accuracy is in-sample vocabulary coverage.
4. **Templated FOMC headlines.** They test transmission, not extraction.
5. **Overlapping windows.** Events cluster; the event-clustered bootstrap helps but does not eliminate dependence.
6. **Revised prices.** Yahoo adjusted closes are not point-in-time; a production version needs CRSP/Compustat or a vendor with vintages.
7. **Authored mechanisms.** The mechanism library is theory- and literature-informed but not preregistered.

## Reproduction

```bash
python -m backend.app.cli backtest --dataset curated  --window-end 1 --out backtest_curated.json
python -m backend.app.cli backtest --dataset fomc     --window-end 1 --out backtest_fomc.json
python -m backend.app.cli backtest --dataset extended --window-end 1 --out backtest_extended.json
```

Compact summaries: `docs/results/backtest_*_summary.json`.

## Versioning

- DMB v1: curated 50.
- DMB v1.1: adds FOMC 58 and extended 92.
- DMB v1.2: adds symbolic proof coverage and ambiguity reporting (v0.4).
- DMB v1.3: adds the surprise-aware FOMC subset (BRW 2021) and the information-effect negative result.
- Future: add CPI/payrolls surprise series, high-frequency Fed-funds/SOFR pricing, and a larger heterogeneous sample.

## License and provenance

- Code: MIT.
- FOMC statements: US government work, public domain; upstream subset from `HusseinKh90/fomc-dataset`.
- Yahoo prices: Yahoo terms; research/educational use only.
- Event labels and mechanism library: project-authored.
