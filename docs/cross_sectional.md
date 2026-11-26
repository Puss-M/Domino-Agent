# Cross-sectional, cost-aware evaluation (E13)

E13 adopts the strongest part of the Qlib / PaCMoE protocol: **rank the
cross-section, use a strong tabular baseline, and evaluate net of costs**. It is
not another direction model; it is a protocol that makes high accuracy claims
falsifiable.

## Protocol

- **Unit**: `(event, asset)` row.
- **Target**: within-event percentile rank of realised `CAR[0,+1]`, not an
  independent up/down label.
- **Features** (strictly pre-event):
  - event: type, direction, magnitude, surprise, confidence, session, sentiment;
  - asset: trailing 20/60-day return, 20/60-day volatility, 60-day beta,
    correlation to SPY/TLT/UUP, distance from 60-day high;
  - market: VIX level and 5-day change;
  - cross-section: within-event rank of momentum, volatility, beta, SPY correlation.
- **Folds**: expanding-window by event date; no event appears in both train and
  test. The audit asserts `feature_end < event_day` for every row.
- **Models**: LightGBM, ridge, momentum, random.
- **Costs**: gross long-short exposure 1; net = gross − 2 × one-way bps. Report
  5/10/20bp.
- **Uncertainty**: event bootstrap for mean long-short return and for the paired
  LightGBM − momentum difference.

## Results (5 folds; 30–60 test events per dataset)

| Dataset | Model | Mean rank IC | Gross L/S | 95% CI | Net @10bp |
|---|---|---:|---:|---|---:|
| Curated | LightGBM | −0.014 | −74.9bp | [−259.1, 91.2] | −94.9bp |
| Curated | Ridge | **+0.089** | **+207.6bp** | **[41.5, 418.2]** | **+187.6bp** |
| Curated | Momentum | +0.081 | +172.4bp | [17.0, 358.1] | +152.4bp |
| Curated | Random | −0.030 | −78.7bp | [−141.7, −28.3] | −98.7bp |
| FOMC | LightGBM | −0.012 | −3.4bp | [−122.9, 105.9] | −23.4bp |
| FOMC | Ridge | +0.016 | +2.2bp | [−110.8, 118.9] | −17.8bp |
| FOMC | Momentum | +0.001 | −3.6bp | [−122.8, 114.8] | −23.6bp |
| FOMC | Random | +0.003 | +18.8bp | [−64.6, 111.0] | −1.2bp |
| Surprise FOMC | LightGBM | +0.072 | +63.1bp | [−43.7, 174.6] | +43.1bp |
| Surprise FOMC | Ridge | +0.030 | −5.1bp | [−153.8, 145.4] | −25.1bp |
| Surprise FOMC | Momentum | −0.015 | −18.3bp | [−141.9, 108.3] | −38.3bp |
| Surprise FOMC | Random | +0.035 | −28.0bp | [−93.0, 31.1] | −48.0bp |
| Extended | LightGBM | −0.038 | −6.8bp | [−101.6, 85.5] | −26.8bp |
| Extended | Ridge | +0.060 | +13.5bp | [−81.3, 96.5] | −6.5bp |
| Extended | Momentum | +0.024 | +66.2bp | [−30.2, 181.0] | +46.2bp |
| Extended | Random | +0.001 | +4.4bp | [−61.9, 72.7] | −15.6bp |

Raw JSON: [`results/cross_sectional_rank.json`](results/cross_sectional_rank.json).

## Interpretation

1. **The curated edge does not replicate.** Ridge and momentum show a positive
   gross long-short on curated (CI excludes zero), but the same models are flat
   or negative on FOMC and extended. A result that appears on one benchmark and
   disappears on the others is not an alpha claim.
2. **LightGBM overfits the small panel.** On 600 rows × 67 features, LightGBM
   does not beat ridge/momentum; on FOMC it is flat. This is exactly the
   "strong tabular baseline first" lesson from Qlib/PaCMoE.
3. **FOMC has no cross-sectional direction signal.** All models are within
   noise and negative after 10bp costs. This is consistent with the event-study
   negative result and the 2026 Audit-Ready ML finding.
4. **Surprise-aware LightGBM is not robust.** +63bp gross on FOMC surprise-aware
   has a CI that crosses zero and does not appear in the other datasets.
5. **Costs matter.** The curated ridge edge survives 10bp costs in this sample,
   but the confidence interval is wide and the sample is 30 test events. Treat
   it as a protocol demonstration, not a tradable result.

## Reproduction

```bash
python scripts/cross_sectional_eval.py
# writes docs/results/cross_sectional_rank.json
```

API:

```text
GET /api/cross-sectional?dataset=curated|fomc|fomc_surprise|extended
```

## Caveats

- 50–92 events, 30–60 test events; wide intervals.
- 67 features on 600 rows is a high-dimensional setting; LightGBM is deliberately
  not tuned on the test folds, so its poor result is a baseline, not a straw man.
- The long-short cost model is an approximation (gross exposure 1, round-trip
  2× one-way cost); it is not an execution simulator.
- p-values are not multiple-testing adjusted across four models and four datasets.
- The target is rank, not a tradeable portfolio; no borrow, capacity, slippage or
  market-impact model.

## What this changes

- The accuracy discussion moves from "which model gets 60.4%?" to "does the
  cross-sectional edge survive folds, costs and other datasets?".
- The answer for Domino today is **no consistent edge**, which is a stronger and
  more credible result than another in-sample accuracy number.
- The next step is not a bigger model; it is more events, intraday features and
  the monetary/information/supply decomposition (E10).
