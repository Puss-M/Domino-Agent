# Evaluation

## Benchmarks

| Dataset | Events | Period | Purpose |
|---|---:|---|---|
| **Curated** | 50 | 2018-03 – 2025-04 | Heterogeneous macro text + transmission |
| **FOMC action-only** | 58 | 2004-06 – 2025-12 | Systematic action-only policy stress test |
| **FOMC surprise-aware** | 45 | 2004-06 – 2025-12 | Direction = BRW (2021) daily surprise sign; \|surprise\| ≥ 2bp |
| **Extended** | 92 | 2004-06 – 2025-12 | Curated + FOMC, deduplicated by type/date |

The FOMC benchmark is generated from official statements by `scripts/build_fomc_events.py`. It includes only non-zero target-range changes and excludes the 2000–2003 statements because their single-value phrasing produced parsing artefacts. Headlines are templated from the parsed range; summaries are statement excerpts; surprise is `neutral` because no high-frequency Fed-funds/SOFR series is bundled.

The benchmark card is [`docs/benchmark.md`](benchmark.md); the model card is [`docs/model_card.md`](model_card.md).

## Protocol

- **Assets**: SPY, QQQ, TLT, IEF, UUP, GLD, XLE, XLU, EEM, HYG, ^VIX, FXI.
- **Primary window**: event day `0` through `+1` trading day.
- **Estimation window**: `[-120, -21]` trading days, market model on SPY.
- **Event-day alignment**: before-open/during → same session; after-close/non-trading → next session.
- **Flat threshold**: 10bp (100bp for ^VIX); flat outcomes are excluded from directional accuracy.
- **Split**: first 50% of events for stack weights and Platt calibration; last 50% held out.
- **Analog maturation**: a prior event enters the analog pool only after its outcome window ends before the current event day.
- **Uncertainty**: 500 bootstrap resamples of **events**; paired Brier comparisons use the same event clusters. The event-study CARs also carry a Kolari–Pynnönen (2010) cross-sectional correlation adjustment; see below.
- **Mechanism anchor**: the stack search allows mechanism weights `0.6–1.2`, analog/base weights `0–0.6`. The anchor is a deliberate prior; the FOMC stress test shows its cost.
- **Temporal integrity**: no LLM sits in the metric path, so the benchmark is not exposed to parametric lookahead (Gao et al., arXiv 2512.23847; Zhang & Stadie, arXiv 2608.02985). It is still exposed to revised Yahoo adjusted closes; the point-in-time contract (E11) is the missing audit.

## Temporal integrity (E11)

The benchmark is **not** a point-in-time reconstruction. The machine-readable
contract is [`backend/data/point_in_time.yaml`](../backend/data/point_in_time.yaml);
the audit is [`docs/point_in_time.md`](point_in_time.md) and
`docs/results/point_in_time.json`.

The LLM-free metric path removes parametric lookahead, but Yahoo adjusted
closes, editorial labels, the FOMC compilation and the ex-post BRW series are
not frozen vintages. Every benchmark therefore returns
`verdict: not_point_in_time` with a dataset-specific culprit list. That is the
honest boundary: the claim is mechanism-level directional skill, not a
deployable point-in-time signal.

## Curated benchmark (primary)

| Model (held-out) | n | Coverage | Accuracy | 95% CI | Brier | AUC | ECE |
|---|---:|---:|---:|---|---:|---:|---:|
| Always-up base rate | 275 | 100% | 0.538 | [0.466, 0.614] | 0.244 | 0.561 | 0.086 |
| Coin flip | 275 | 100% | — | — | 0.250 | 0.500 | 0.042 |
| Mechanism only | 254 | 92.4% | 0.614 | [0.553, 0.675] | 0.259 | 0.613 | 0.117 |
| Analog only | 192 | 69.8% | 0.586 | [0.478, 0.674] | 0.248 | 0.581 | 0.112 |
| Hybrid (mech + analog) | 265 | 96.4% | 0.621 | [0.563, 0.682] | 0.258 | 0.625 | 0.135 |
| Stacked | 265 | 96.4% | 0.596 | [0.531, 0.651] | 0.238 | 0.634 | 0.094 |
| **Stacked + Platt** | **265** | **96.4%** | **0.604** | **[0.537, 0.668]** | **0.238** | **0.634** | **0.052** |

### Paired comparisons (Brier, event-clustered)

| Comparison | ΔBrier | 95% CI | One-sided p | n pairs |
|---|---:|---|---:|---:|
| Stacked + Platt vs always-up | −0.0082 | [−0.0235, 0.0055] | 0.128 | 265 |
| Stacked + Platt vs mechanism | −0.0212 | [−0.0467, 0.0038] | 0.048 | 254 |
| Mechanism vs always-up | +0.0116 | [−0.0277, 0.0459] | 0.736 | 254 |

Negative ΔBrier means the first model is better. The improvement over the base rate is **not statistically significant** at 5%; the improvement over the overconfident mechanism-only model is marginal. This is the honest read of a 50-event sample.

## FOMC stress test

| Model (held-out) | n | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|---:|
| Always-up base rate | 319 | 100% | **0.566** | 0.250 | 0.544 |
| Mechanism only | 297 | 93.1% | **0.411** | 0.384 | 0.416 |
| Analog only | 297 | 93.1% | 0.524 | 0.262 | 0.506 |
| Mechanism calibrated | 297 | 93.1% | 0.539 | 0.250 | 0.416 |
| Stacked + Platt | 297 | 93.1% | 0.412 | 0.255 | 0.404 |

Paired Brier, mechanism vs base rate: **+0.1338**, 95% CI **[0.076, 0.180]**, one-sided p=**1.0**. The mechanism prior is significantly worse than a naive base rate on action-only FOMC events.

Why:

- A policy action is not a surprise. A 25bp hike that was fully priced is not a hawkish shock.
- The same “hike = risk-off” sign cannot hold across regimes: 2004–2006 hikes were telegraphed normalization, 2007–2008 cuts were a recession/funding shock, 2022 hikes were an inflation shock.
- Calibration improves the Brier score (0.384 → 0.250) but cannot fix the sign. The missing input is high-frequency Fed-funds/SOFR pricing and positioning.
- Per-asset FOMC accuracy is weakest on TLT (0.370), IEF (0.333), UUP (0.385), HYG (0.348), ^VIX (0.333). The model is not merely noisy; it is systematically on the wrong side of the policy-pricing effect.

This is a **documented failure boundary**. A production version should abstain or use base rates on action-only FOMC until a surprise provider is wired in.

## Surprise-aware FOMC

A natural objection to the action-only failure is that we ignored the surprise. We tested the standard free fix: join the benchmark with the **Bu, Rogers & Wu (2021, JME)** daily shock series (`brw_ext`), set direction to the sign of the surprise, and drop events with |surprise| < 2bp (45 remain).

| Model (held-out) | n | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|---:|
| Always-up base rate | 256 | 100% | **0.527** | 0.255 | 0.509 |
| Mechanism (surprise direction) | 254 | 99.2% | **0.453** | 0.355 | 0.450 |
| Stacked + Platt | 254 | 99.2% | 0.453 | 0.253 | 0.450 |

By surprise sign: **tightening surprises 52.2%**, **easing surprises 43.3%**. A dovish surprise is not automatically risk-on; it can be an **information shock** (the Fed sees a weaker economy), which is the Nakamura–Steinsson (2018) information effect. Separating monetary from information shocks requires intraday rate-equity co-movement (Jarociński & Karadi 2020); a daily surprise sign cannot do it. A 2026 supply-side result (SSRN 7633199) adds a third component: supply conditions enter surprises through rate–exchange-rate comovement, so the right decomposition is monetary / information / supply, not just the first two.

This is a stronger negative result than the action-only one: even a published surprise series does not rescue 1-day asset direction. It also defines the next experiment precisely — not "add a surprise number", but "decompose the surprise".

## Extended benchmark

| Model (held-out) | n | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|---:|
| Always-up base rate | 509 | 100% | 0.541 | 0.253 | 0.536 |
| Mechanism only | 475 | 93.3% | 0.575 | 0.283 | 0.562 |
| Analog only | 336 | 66.0% | 0.564 | 0.258 | 0.551 |
| Stacked + Platt | 490 | 96.3% | 0.508 | 0.248 | 0.578 |

No model dominates. The mechanism has an accuracy advantage but is overconfident; the calibrated stack has the best Brier but loses accuracy. The mixed benchmark is reported for completeness, not as a headline.

## Five-day robustness (curated)

| Model | n | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|---:|
| Always-up | 287 | 100% | 0.470 | 0.260 | 0.455 |
| Mechanism only | 266 | 92.7% | 0.568 | 0.283 | 0.560 |
| Analog only | 203 | 70.7% | 0.444 | 0.287 | 0.416 |
| Stacked + Platt | 277 | 96.5% | 0.545 | 0.252 | 0.528 |

The five-day horizon is materially weaker than the one-day announcement window. Macro information is largely priced in the first session; subsequent drift is dominated by other news. The project does not claim a five-day trading signal.

## Symbolic ablation (E6)

E6 asks whether the symbolic layer adds **predictive** value on top of the
numeric mechanism model, or whether its value is auditability. The arms are:

- **Numeric only**: the mechanism prior (`p_mech`).
- **Symbolic only**: a fixed 0.8 probability for a proved positive direction,
  0.2 for a proved negative direction, abstain otherwise.
- **Symbolic gated**: keep `p_mech` only when the proof is proved and does not
  contradict the numeric direction; abstain on `ambiguous` / `not_entailed`.
- **Symbolic blend**: equal-weight logit blend of `p_mech` and the symbolic
  signal when both exist; fall back to whichever exists.

| Dataset | Model | n | Coverage | Accuracy | Brier | AUC |
|---|---|---:|---:|---:|---:|---:|
| Curated | Numeric only | 254 | 92.4% | 61.4% | 0.259 | 0.613 |
| Curated | Symbolic only | 172 | 62.5% | 60.5% | 0.277 | 0.608 |
| Curated | Symbolic gated | 172 | 62.5% | 60.5% | 0.273 | 0.589 |
| Curated | Symbolic blend | 254 | 92.4% | 61.4% | 0.258 | 0.610 |
| Curated | Stacked + Platt | 265 | 96.4% | 60.4% | 0.238 | 0.634 |
| FOMC | Numeric only | 297 | 93.1% | 41.1% | 0.384 | 0.416 |
| FOMC | Symbolic only | 181 | 56.7% | 41.4% | 0.391 | 0.408 |
| FOMC | Symbolic gated | 181 | 56.7% | 41.4% | 0.383 | 0.403 |
| FOMC | Symbolic blend | 297 | 93.1% | 41.1% | 0.386 | 0.410 |

Paired Brier, symbolic blend vs numeric only: curated **−0.0002** (95% CI
−0.0073–0.0072, p=0.52, n=254); FOMC **+0.0025** (95% CI −0.0013–0.0067,
p=0.89, n=297). Neither is significant. Symbolic-only vs numeric only on
covered pairs: curated **+0.0043** (95% CI −0.0153–0.0241, p=0.68), FOMC
**+0.0087** (95% CI −0.0032–0.0222, p=0.92); the symbolic arm is not better.

Other benchmarks show the same pattern:

| Benchmark | Numeric accuracy | Symbolic accuracy (coverage) | Blend ΔBrier vs numeric |
|---|---:|---:|---:|
| Curated 5-day | 56.8% | 57.1% (63.4%) | +0.0002 (p=0.54) |
| FOMC surprise-aware | 45.3% | 44.0% (58.6%) | +0.0033 (p=0.87) |
| Extended | 57.5% | 57.1% (60.5%) | +0.0018 (p=0.75) |

The gated arm's paired delta is **0.0 by construction**: it keeps the numeric
probability on covered pairs. Its difference is coverage — it abstains on
30–43% of assets — not calibration.

This is a **negative ablation for predictive skill**. The symbolic layer does
not improve direction or Brier on these benchmarks. Its value is:
structured ambiguity (37.5% of curated active predictions are not certified),
a minimal proof core per proved asset, and a formal gate that can contradict a
narrative. That is the honest claim; the paper should not sell E6 as an accuracy
win.

## Cross-sectional rank and costs (E13)

E13 changes the target from 12 independent up/down labels to the **within-event
percentile rank of CAR[0,+1]**, following the Qlib/PaCMoE protocol. It uses
strictly pre-event features, expanding-window event folds, LightGBM/ridge/
momentum/random baselines, and net long-short returns at 5/10/20bp. Full protocol
and caveats: [`cross_sectional.md`](cross_sectional.md).

| Dataset | Best model | Mean rank IC | Gross L/S | 95% CI | Net @10bp |
|---|---|---:|---:|---|---:|
| Curated | Ridge | +0.089 | +207.6bp | [41.5, 418.2] | +187.6bp |
| FOMC | Ridge | +0.016 | +2.2bp | [−110.8, 118.9] | −17.8bp |
| FOMC surprise-aware | LightGBM | +0.072 | +63.1bp | [−43.7, 174.6] | +43.1bp |
| Extended | Momentum | +0.024 | +66.2bp | [−30.2, 181.0] | +46.2bp |

The curated edge **does not replicate** on FOMC or extended; LightGBM overfits
the 600-row panel; FOMC is flat/negative after costs. The honest read is **no
consistent cross-sectional direction edge**. This is the same boundary the
2026 Audit-Ready ML paper finds with 41 causal folds: direction is hard,
volatility/risk is more predictable.

## Cross-sectional correlation and clustering (E7)

Macro events hit all assets at once. A naive event-study t-statistic that treats
the 12 assets as independent cross-sectional observations overstates precision.
We implement the Kolari–Pynnönen (2010) adjustment of the Boehmer–Musumeci–
Poulsen standardized CAR test:

`KP_t = BMP_t / sqrt(1 + (N - 1) * rho_bar)`

where `N` is the number of assets in the event cross-section and `rho_bar` is
the average pairwise correlation of market-model residuals over `[-120, -21]`.
SPY is excluded from the cross-section because its market-model residual is zero
by construction. Critical values are two-sided 5% t with `N - 1` degrees of
freedom, not 1.96.

| Dataset | Events | Mean rho | Inflation | Mean \|BMP\| | Mean \|KP\| | Sig. BMP | Sig. KP | Pooled t (naive → KP) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Curated | 50 | 0.043 | 1.19 | 1.18 | 1.01 | 6.0% | 6.0% | 1.92 → 1.65 |
| FOMC action-only | 58 | 0.059 | 1.23 | 1.24 | 1.01 | 6.9% | 3.5% | 0.25 → 0.21 |
| FOMC surprise-aware | 45 | 0.057 | 1.22 | 1.29 | 1.06 | 8.9% | 4.4% | −0.38 → −0.33 |
| Extended | 92 | 0.054 | 1.22 | 1.23 | 1.02 | 7.6% | 5.4% | 1.35 → 1.14 |

Raw numbers: [`docs/results/kp_test.json`](results/kp_test.json).

The adjustment is modest because residual correlation after the market model is
low (0.04–0.06), not because the correction is unnecessary. It still moves the
FOMC significant-event share from 6.9% to 3.5%. More importantly, **no pooled
equal-weighted CAR is significant in any benchmark** after adjustment. Macro
events do not produce a common one-day cross-asset move in this sample; their
effects are heterogeneous by asset. That is consistent with the per-asset
pattern below and with the paper's claim that the useful object is the signed
transmission path, not an average market reaction.

The primary directional inference does **not** rely on these CAR t-statistics.
It uses event-clustered bootstrap intervals over Brier scores and accuracy,
which already preserve within-event cross-asset correlation. E7 is a robustness
check on the event-study layer, not a second test of the model's skill.

Per-asset means also get a cluster-robust t that collapses same-day events. The
largest curated values are QQQ **+43.5bp** (t=3.22), XLE **−120.8bp** (t=−2.98),
GLD **+62.7bp** (t=2.56) and UUP **−32.6bp** (t=−2.39). XLE is negative and
significant in all four datasets (curated t=−2.98, FOMC t=−2.23, surprise-aware
t=−2.49, extended t=−3.17). These are unconditional sample means, not
multiple-testing-adjusted discoveries; they describe which assets moved, not
what the model predicted.

## Per-asset (curated, headline model, held-out)

| Asset | n | Accuracy | Brier | Mean CAR |
|---|---:|---:|---:|---:|
| SPY | 23 | 0.783 | 0.214 | +7bp |
| TLT | 25 | 0.720 | 0.229 | +59bp |
| IEF | 24 | 0.708 | 0.237 | +49bp |
| UUP | 24 | 0.750 | 0.219 | −41bp |
| GLD | 20 | 0.650 | 0.235 | +88bp |
| XLE | 23 | 0.565 | 0.244 | −112bp |
| EEM | 21 | 0.571 | 0.234 | +43bp |
| HYG | 20 | 0.550 | 0.243 | +5bp |
| ^VIX | 19 | 0.526 | 0.235 | +471bp |
| FXI | 24 | 0.500 | 0.257 | +92bp |
| QQQ | 21 | 0.429 | 0.250 | +48bp |
| XLU | 21 | 0.429 | 0.258 | −1bp |

## Per-event-type (curated, headline model, held-out)

| Event type | Events | Predictions | Accuracy | Brier |
|---|---:|---:|---:|---:|
| Financial stability | 1 | 10 | 0.800 | 0.207 |
| Trade policy | 2 | 23 | 0.696 | 0.239 |
| Labour market | 1 | 6 | 0.667 | 0.229 |
| Inflation | 5 | 53 | 0.642 | 0.234 |
| Monetary policy | 10 | 107 | 0.598 | 0.237 |
| China policy | 2 | 21 | 0.571 | 0.230 |
| Energy supply | 2 | 23 | 0.565 | 0.252 |
| Geopolitics | 2 | 22 | 0.409 | 0.255 |

Small cells (1–2 events) are descriptive, not inferential.

## Calibration

Quantile bins for the curated headline model (265 held-out predictions):

| Predicted range | n | Mean predicted | Observed up-frequency |
|---|---:|---:|---:|
| 0.425–0.454 | 33 | 0.438 | 0.424 |
| 0.454–0.469 | 33 | 0.462 | 0.515 |
| 0.470–0.491 | 33 | 0.479 | 0.394 |
| 0.491–0.509 | 33 | 0.498 | 0.333 |
| 0.512–0.543 | 33 | 0.530 | 0.576 |
| 0.543–0.560 | 33 | 0.553 | 0.636 |
| 0.560–0.572 | 33 | 0.566 | 0.697 |
| 0.572–0.590 | 34 | 0.581 | 0.706 |

The top of the distribution is monotonic and close to the diagonal; the middle is noisy. With 33 predictions per bin and correlated assets within events, this is expected. The equal-width ECE (`0.052`) is the headline calibration number; the quantile bins are for visual resolution, not a second score. The FOMC calibrated probabilities are compressed toward 0.5 and remain anti-correlated with outcomes (AUC 0.416); calibration cannot repair a wrong conditional mean.

## Failure cases

1. **FOMC action-only events.** Mechanism accuracy 41.1% vs base 56.6%; significant negative skill.
2. **FOMC surprise-aware events.** Even with the BRW (2021) daily surprise, mechanism accuracy is 45.3% vs base 52.7%; tightening surprises 52.2%, easing surprises 43.3%. The missing input is the monetary/information/supply decomposition, not just a surprise number (SSRN 7633199).
3. **QQQ (42.9%) and XLU (42.9%) on curated.** The engine over-predicts duration-sensitive downside around hikes; QQQ's mean 1-day CAR is **+48bp** in this sample.
4. **FXI (50.0%).** Two China policy events; stimulus transmission is regime-dependent.
5. **Geopolitics (40.9%).** Two events; the 1-day equity sign is noisy even when the safe-haven direction is right.
6. **Five-day horizon.** The edge decays; accuracy 54.5%, AUC 0.528.
7. **Calibration middle bins.** Under-confident in some bins, over-confident in others; the sample is too small for a richer calibrator.

## Reproduction

```bash
python -m backend.app.cli backtest --dataset curated  --window-end 1 --out backtest_curated.json
python -m backend.app.cli backtest --dataset curated  --window-end 5 --out backtest_curated_5d.json
python -m backend.app.cli backtest --dataset fomc     --window-end 1 --out backtest_fomc.json
python -m backend.app.cli backtest --dataset fomc_surprise --window-end 1 --out backtest_fomc_surprise.json
python -m backend.app.cli backtest --dataset extended --window-end 1 --out backtest_extended.json
```

Compact summaries are checked in at:

- `docs/results/backtest_curated_1d_summary.json`
- `docs/results/backtest_curated_5d_summary.json`
- `docs/results/backtest_fomc_1d_summary.json`
- `docs/results/backtest_fomc_surprise_1d_summary.json`
- `docs/results/backtest_extended_1d_summary.json`

Each response includes every event, every asset prediction, the realized CAR, the analog sample size, the stack weights, the Platt parameters and the paired comparisons.
