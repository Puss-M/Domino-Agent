# Evaluation

## Protocol

- **Sample**: 50 dated events, 2018-03-22 to 2025-04-09. Event types: monetary policy (21), inflation (9), trade policy (6), geopolitics (4), energy supply (3), financial stability (2), China policy (2), labour market (2), fiscal policy (1).
- **Assets**: SPY, QQQ, TLT, IEF, UUP, GLD, XLE, XLU, EEM, HYG, ^VIX, FXI.
- **Primary window**: event day `0` through `+1` trading day.
- **Estimation window**: `[-120, -21]` trading days, market model on SPY.
- **Event-day alignment**: before-open/during → same session; after-close/non-trading → next session.
- **Flat threshold**: 10bp (100bp for ^VIX); flat outcomes are excluded from directional accuracy.
- **Split**: first 50% of events for stack weights and Platt calibration; last 50% held out.
- **Analog maturation**: a prior event enters the analog pool only after its outcome window ends before the current event day.
- **Uncertainty**: 500 bootstrap resamples of **events**.

## Headline results (1-day window)

| Model (held-out) | n | Coverage | Accuracy | 95% CI | Brier | AUC | ECE |
|---|---:|---:|---:|---|---:|---:|---:|
| Always-up base rate | 275 | 100% | 0.538 | [0.466, 0.614] | 0.244 | 0.561 | 0.086 |
| Coin flip | 275 | 100% | — | — | 0.250 | 0.500 | 0.042 |
| Mechanism only | 254 | 92.4% | 0.614 | [0.553, 0.675] | 0.259 | 0.613 | 0.117 |
| Analog only | 192 | 69.8% | 0.586 | [0.478, 0.674] | 0.248 | 0.581 | 0.112 |
| Hybrid (mech + analog) | 265 | 96.4% | 0.621 | [0.563, 0.682] | 0.258 | 0.625 | 0.135 |
| Stacked | 265 | 96.4% | 0.596 | [0.531, 0.651] | 0.238 | 0.634 | 0.094 |
| **Stacked + Platt** | **265** | **96.4%** | **0.604** | **[0.537, 0.668]** | **0.238** | **0.634** | **0.052** |

Read this table carefully:

- The **mechanism-only** model has better raw accuracy than the calibrated stack, but its probabilities are overconfident: Brier `0.259` vs `0.238`, ECE `0.117` vs `0.052`.
- The **hybrid** model has the highest raw accuracy (`0.621`) but also overconfident probabilities (`Brier 0.258`, `ECE 0.135`).
- The **stacked + Platt** model is selected for probability quality, not for the highest accuracy. The 95% interval for accuracy still excludes 0.50, but the interval is wide.
- **Coverage** is not 100%: the engine abstains when no mechanism matches or confidence is too low. Coverage is reported as a feature.

## Five-day robustness

| Model | n | Coverage | Accuracy | Brier | AUC |
|---|---:|---:|---:|---:|---:|
| Always-up | 287 | 100% | 0.470 | 0.260 | 0.455 |
| Mechanism only | 266 | 92.7% | 0.568 | 0.283 | 0.560 |
| Analog only | 203 | 70.7% | 0.444 | 0.287 | 0.416 |
| Hybrid | 277 | 96.5% | 0.564 | 0.291 | 0.538 |
| Stacked | 277 | 96.5% | 0.556 | 0.272 | 0.528 |
| **Stacked + Platt** | **277** | **96.5%** | **0.545** | **0.252** | **0.528** |

The five-day horizon is materially weaker. This is the expected result if macro information is priced in the first session and subsequent drift is dominated by other news. It is reported rather than hidden.

## Per-asset (headline model, held-out, 1-day)

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

## Per-event-type (headline model, held-out, 1-day)

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

Quantile bins for the headline model (`stacked + Platt`, 265 held-out predictions):

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

The top of the distribution is monotonic and close to the diagonal; the middle is noisy. With 33 predictions per bin and correlated assets within events, this is expected. The equal-width ECE (`0.052`) is the headline calibration number; the quantile bins are for visual resolution, not a second score.

## Extraction

- Joint event-type + direction accuracy: **50/50** on the curated event sample.
- Confusion matrix: diagonal for all event types.
- This is **in-sample vocabulary coverage**. The headlines and lexicons were developed together; it is not an out-of-distribution benchmark. An OOD test would use held-out outlets, languages, and event types.

## Failure cases

1. **QQQ (42.9%) and XLU (42.9%).** The engine over-predicts duration-sensitive downside around hikes. QQQ's mean 1-day CAR is **+48bp** in this sample; growth equities often rallied after in-line hikes and during the 2024 easing cycle. The base-rate and analog components do not fully offset the mechanism prior.
2. **FXI (50.0%).** China policy events have two observations, and the transmission is regime-dependent (stimulus credibility, property stress, FX). The mechanism is too coarse.
3. **Geopolitics (40.9%).** Two events, and the 1-day sign is dominated by whether the initial risk-off move holds into the close. The safe-haven channel direction is right more often than the equity sign.
4. **Five-day horizon.** The edge decays; the 5-day accuracy is 54.5% and the AUC is 0.528. The project does not claim a 5-day trading signal.
5. **Calibration middle bins.** The model is under-confident in some middle bins and over-confident in others. The sample is too small to fit a richer calibrator.

## Reproduction

```bash
# 1-day primary
python -m backend.app.cli backtest --window-end 1 --out backtest_1d.json

# 5-day robustness
python -m backend.app.cli backtest --window-end 5 --out backtest_5d.json

# event-study summary only
curl http://127.0.0.1:8000/api/event-study?window_end=1
```

The full backtest response includes every event, every asset prediction, the realized CAR, the analog sample size, the stack weights, and the Platt parameters. The compact summaries used in this document are checked in at `docs/results/backtest_1d_summary.json` and `docs/results/backtest_5d_summary.json`.
