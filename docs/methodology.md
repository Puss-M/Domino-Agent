# Methodology

This document explains what the engine computes, why each choice was made, and where the result should not be trusted. The short version: **the language model is not the model**. The model is a cited transmission library plus a small, evaluated statistical layer.

### Why not LLM agents?

The original prototype used two LLM personas, a creative “Detective” and a conservative “Reviewer.” That is a useful demo and a weak control system: the reviewer has no external evidence, no deterministic checks, and no way to fail a build. v0.3 keeps the role separation but turns each role into a typed contract:

- **Extractor**: deterministic parsing of numbers, units, entities and surprise.
- **Retriever**: cited mechanism matching with explicit inclusion/exclusion conditions.
- **Auditor**: citation, grade, sign-conflict and look-ahead checks that can fail a run.
- **Quantifier**: channel/loading aggregation and probability construction.
- **Reporter**: memo assembled from the structured result.

An LLM is optional and, if added, is confined to narration. It cannot change a number, a sign, an edge or a citation. This is a deliberate trade: less “agent theater,” more auditable financial logic.

---

## 0. Datasets

| Dataset | Events | Period | Role |
|---|---:|---|---|
| `curated` | 50 | 2018-03 – 2025-04 | Heterogeneous text + transmission |
| `fomc` | 58 | 2004-06 – 2025-12 | Systematic action-only stress test |
| `extended` | 92 | 2004-06 – 2025-12 | Curated + FOMC, deduplicated |

The curated set is the extraction benchmark; the FOMC set is the transmission stress test. The FOMC headlines are templated from the target range, so they are excluded from extraction metrics. The detailed benchmark card is [`benchmark.md`](benchmark.md).

---

## 1. Event extraction

### 1.1 Why rules first

A macro event has a small number of decision-relevant fields: type, direction, actor, magnitude, surprise. Those fields are too important to leave to a generative parser. The extractor is a deterministic scorer over domain lexicons; it is testable, reproducible, and exposes the keywords behind each decision.

The extractor does **not** pretend to understand arbitrary text. When no event type scores above zero, it returns `other` with low confidence, and the reasoning layer abstains.

### 1.2 Units

All unit-bearing numbers are normalized at the boundary:

| Input | Normalized |
|---|---|
| `50bp`, `50 basis points`, `50个基点` | `50 bps` |
| `0.5 percentage points`, `0.5个百分点` | `0.5 pp` |
| `8.6%`, `8.6 percent` | `8.6 pct` |
| `$1.9 trillion` | `1900 usd_bn` |
| `$300 million` | `0.3 usd_bn` |
| `2 million barrels per day`, `2 mb/d`, `200万桶/日` | `2.0 mbpd` |

`best_magnitude` chooses the unit that matters for the event type: bps for monetary policy, pp/pct for inflation, mb/d for energy supply, USD bn for trade/fiscal.

### 1.3 Surprise vs level

This is the most important financial distinction in the pipeline.

- A `75bp` hike is a policy action. A `75bp` hike when the market priced `50bp` is a `+25bp` surprise.
- A CPI print of `8.6%` is a level. `8.6% vs 8.3% expected` is a `+0.3pp` surprise.

The canonical `Surprise` object stores the magnitude, unit, raw phrase, and a sign defined as:

> `positive` = **more of the event direction than expected**.

Thus a surprise hike and a surprise cut can both be positive on their respective directions. A fully priced action is `neutral`, and the audit warns that a level change may already be in the price.

The current event sample uses curated surprise labels from published consensus for CPI and qualitative surprise for policy/geopolitical events. This is a known limitation: a production system would use high-frequency Fed-funds/SOFR futures or a vendor surprise series.

### 1.4 Entities

The vocabulary is intentionally controlled:

- `Fed`, `FOMC`, `Federal Reserve`, `美联储` → `US_FED`
- `ECB`, `European Central Bank` → `ECB`
- `BOJ`, `Bank of Japan` → `BOJ`
- `PBOC`, `中国人民银行` → `PBOC`
- `OPEC+`, `OPEC`, `欧佩克` → `OPEC_PLUS`
- `oil`, `crude`, `Brent`, `WTI`, `原油` → `ENERGY`
- `tech stocks`, `Nasdaq`, `科技股` → `TECH`

Longest match wins, spans cannot overlap, and ASCII aliases use word boundaries. Anything outside the vocabulary is reported as unmatched rather than silently linked.

### 1.5 Sentiment

The shipped lexicon is a small, auditable seed with four axes:

- polarity (positive/negative),
- uncertainty,
- hawkish/dovish,
- risk-on/risk-off.

It handles negation within a three-token window, intensifiers (`sharply`, `slightly`), and Chinese terms with a preceding `不/未/无`. The official Loughran–McDonald dictionary is **not** redistributed; if you have a licensed copy, set `DOMINO_LM_DICTIONARY` and it is merged into the seed.

Sentiment is a feature, not a verdict. A headline can be negative in tone but hawkish in policy direction; the extractor and mechanism library decide what that means for a specific channel.

### 1.6 Deduplication

Syndicated headlines are clustered with a combination of:

- 3-gram shingle Jaccard,
- a character-level similarity ratio, gated on at least 20% token overlap.

The gate prevents short unrelated headlines from looking similar because they share letters. Each cluster reports duplicate count, source diversity, and a novelty score. The current demo snapshot shows 20 GDELT items collapsing to 10 clusters.

---

## 2. Cited mechanism library

### 2.1 Structure

The library (`backend/data/knowledge/mechanisms.yaml`) has two layers:

- **Channels**: real yields, nominal yields, discount rates, USD, risk premium, credit spreads, oil price, inflation expectations, growth expectations, policy support, China demand, funding liquidity, safe haven, energy costs.
- **Mechanisms**: event-type + direction + condition → signed channel weights.

A mechanism must have:

- at least one event type and direction,
- a confidence,
- an evidence grade (`A`–`D`),
- a rationale,
- at least one citation,
- channel weights in `[-1.5, 1.5]`.

A channel must have:

- at least one citation,
- loadings for the assets it affects,
- an illustrative scale in basis points.

The scale is explicitly **not** an estimated elasticity. It converts a unitless channel score into an order-of-magnitude 5-day prior, nothing more.

### 2.2 Retrieval

For an event, a mechanism is eligible only if:

1. the event type is in its `event_types`;
2. the direction is in its `directions` (unless the list is empty);
3. the actor matches if `actors` is specified;
4. all `any_keywords` conditions have at least one hit (if the list is non-empty);
5. no `none_keywords` exclusion is present.

The match score starts at the mechanism confidence and adds small bonuses for actor specificity and condition hits. Actor-specific mechanisms suppress generic mechanisms for the same event type: a BOJ hike uses the funding-liquidity mechanism, not the Fed real-yield mechanism.

If no mechanism matches, the engine does not call an LLM to fill the gap. It abstains.

### 2.3 Aggregation

Let `r_m` be the retrieval score of mechanism `m`, and `w_mc` its signed weight on channel `c`.

Channel activation:

```
s_c = Σ_m w_mc r_m  /  max(1, Σ_m |w_mc r_m|)
```

The denominator saturates agreement at ±1 but preserves disagreement: two mechanisms with opposite signs produce a small net score, not a large one.

Asset score:

```
x_a = tanh(0.6 * Σ_c s_c L_{c,a})
```

`L_{c,a}` is the asset loading on channel `c` (e.g. TLT is −1.0 on real yields; UUP is +1.0 on the dollar). The `tanh` prevents a one-sided asset from being forced to ±1; a strong but not unanimous transmission stays around ±0.6.

Probability:

```
p_up = 0.5 + 0.45 * tanh(1.5 * x_a)
```

Expected 5-day CAR prior:

```
E[CAR_a] = 0.5 * Σ_c s_c L_{c,a} scale_c * strength
```

`strength` is a bounded function of the surprise/magnitude (0.5–2.0). It changes the magnitude prior and the displayed confidence, not the sign.

### 2.4 Evidence grades

- **A**: peer-reviewed/official mechanism, directly applicable, conditions met.
- **B**: empirical support but regime/condition uncertainty.
- **C**: plausible but weak; allowed with a confidence penalty.
- **D**: speculative; never allowed to drive a headline prediction.

Conflicting channels downgrade the asset grade one notch and reduce confidence proportionally to the conflict share. The audit also flags any asset whose only support is C-grade.

### 2.5 Where the mechanism fails: action-only FOMC

The FOMC stress test is deliberately homogeneous: 58 target-range changes, no surprise measure. The mechanism prior achieves **41.1%** directional accuracy, while an always-up base rate achieves **56.6%**. The paired Brier difference is **+0.1338** (95% CI 0.076–0.180): the prior is significantly worse than a naive baseline.

The reason is economic, not statistical. A policy action is not a surprise. The same hike sign cannot be right for 2004–2006 normalization, 2007–2008 recession cuts and 2022 inflation-shock hikes. Calibration improves the Brier score but cannot repair the sign. The missing input is high-frequency Fed-funds/SOFR pricing and positioning. The system should abstain or use base rates on action-only FOMC until that input exists.

### 2.6 Graph semantics

```
event → channel → asset
```

- `event → channel` sign = sign of the mechanism's channel weight. The frontend renders these as neutral “channel link” edges to avoid confusing “channel rises” with “asset rises”.
- `channel → asset` sign = sign of the asset loading. These are the colored bullish/bearish edges.
- Every edge carries the mechanism ID, evidence grade, rationale, and citations.

---

## 3. Evidence audit

The audit is deterministic and fails the run on any of the following:

- no mechanism matched;
- extraction confidence below 0.35;
- a `D`-grade mechanism entered a prediction;
- a mechanism has no citation;
- an edge has no citation;
- an event is dated after the analysis as-of time (look-ahead);
- all assets abstained.

It warns on:

- no source URL;
- a monetary/inflation event with no explicit surprise direction;
- a large share of abstentions;
- conflicting channels;
- C-grade evidence driving an asset.

The audit is not a proof of correctness. It is a set of checks that can fail a build, which is more than a reviewer prompt can do.

---

## 4. Event study

### 4.1 Alignment

The event day is the first trading session that can price the news:

- `before_open` / `during`: same session if it is a trading day, otherwise the next session.
- `after_close` / `non_trading`: the next session.

This matters: a Sunday OPEC announcement or a 16:00 ET tariff speech must not be credited to Friday's close.

### 4.2 Abnormal returns

Market model on the estimation window `[-120, -21]`:

```
R_it = α_i + β_i R_mt + ε_it
AR_it = R_it - (α_i + β_i R_mt)
CAR_i[0,T] = Σ AR_it
```

`R_mt` is SPY. For SPY itself, the market-model residual is zero by construction, so SPY is evaluated on its raw return. The primary window is `[0, +1]` because macro information is largely priced in the first session; `[0, +5]` is reported as robustness.

A `flat` outcome is defined as `|CAR| < 10bp` (100bp for VIX). Flat outcomes are excluded from directional accuracy but counted in coverage denominators.

### 4.3 What the evaluation is not

- It does not model transaction costs, slippage, borrow, or capacity.
- It does not use a point-in-time price database; Yahoo adjusted closes are revised.
- It does not correct for overlapping event windows beyond clustering the bootstrap by event.
- It does not identify a structural causal effect. It tests whether the signed transmission hypothesis matched realized abnormal returns.

---

## 5. Walk-forward backtest

### 5.1 No look-ahead in analogs

For event `i`, the analog model is fitted only on events `j < i` whose outcome window has **fully matured** before event `i`'s event day. A prior event whose 5-day window is still open cannot contribute.

The analog model buckets by event type and direction (with hawkish hold grouped into tightening and dovish hold into easing), then estimates a Beta-smoothed up-probability per asset:

```
p_up = (up_count + 1.5) / (n + 3)
```

It abstains when `n < 2`.

### 5.2 Baselines

- **Always-up base rate**: expanding per-asset up-frequency from matured prior events, Laplace-smoothed.
- **Coin flip**: `p = 0.5`.
- **Mechanism only**: the transmission model's `p_up`.
- **Analog only**: the historical analog model.
- **Hybrid**: `sigmoid(logit(p_mech) + 0.5 logit(p_analog))`.
- **Stacked**: `sigmoid(w_m logit(p_mech) + w_a logit(p_analog) + w_b logit(p_base))`, with non-negative weights selected on the training half by Brier score.
- **Calibrated**: Platt scaling `sigmoid(a logit(p) + b)` fitted on the training half.

The mechanism weight is constrained to `[0.6, 1.2]` by the evidence prior; analog/base weights are fitted on the training half. On the curated 1-day run the stack selected `w_m=0.60`, `w_a=0.40`, `w_b=0.40`, with Platt `a=0.34`, `b=0.05`. On the FOMC stress test it selected `w_m=0.60`, `w_a=0.60`, `w_b=0.00`, and the result is still negative skill. These values are printed in the backtest response; they are not hard-coded into the engine.

### 5.3 Metrics

- **Directional accuracy**: `p_up > 0.5` predicts up; `p_up < 0.5` predicts down; `0.5` is not scored.
- **Brier**: mean squared probability error.
- **AUC**: rank discrimination, tie-aware.
- **ECE**: expected calibration error over equal-width bins; the reliability plot uses quantile bins for resolution.
- **Coverage**: non-abstain share of non-flat outcomes.
- **Confidence interval**: percentile bootstrap resampling **events**, not asset rows.
- **Paired Brier comparison**: resample events, compute the Brier difference on paired `(event, asset)` rows, report a 95% interval and a one-sided p-value. Negative means the first model is better.

---

## 6. Threats to validity

1. **Small samples.** 50 curated events and 58 FOMC events; 25–29 events in each held-out half. The confidence intervals are wide.
2. **Curated labels.** Event type/direction labels are editorial. Extraction accuracy is in-sample vocabulary coverage, not an OOD benchmark.
3. **Authored priors.** The mechanism library was written by the project with knowledge of the literature and history, though not fitted to the test outcomes. It is not preregistered.
4. **Revised prices.** Adjusted closes are not point-in-time. A production backtest should use CRSP/Compustat or a vendor with vintages.
5. **Overlapping windows.** Events can cluster (e.g. CPI and FOMC in the same month). The cluster bootstrap helps but does not eliminate cross-event dependence.
6. **Surprise measurement.** CPI surprises are curated; FOMC surprises are qualitative in most events. A real desk would use high-frequency futures. The FOMC stress test exists to make this limitation measurable: the mechanism prior is significantly worse than a base rate when the action is all you know.
7. **No execution model.** The event study is an evaluation harness, not a P&L.

The correct claim is: **on the 50-event curated sample, the calibrated stack produced 60.4% directional views and a Brier of 0.238, but the improvement over the base rate is not statistically significant; on the 58-event action-only FOMC stress test, the mechanism prior is significantly worse than the base rate.** Not: “the model predicts markets.” The FOMC failure is the main research result and the reason the next step is surprise data, not more prompt engineering.

---

## 7. How to extend

- **Add a mechanism**: add a YAML entry with a citation, channels, conditions and a grade; add a retrieval test; run the backtest and inspect whether it changes the sign for the relevant assets.
- **Add an event**: add a dated YAML entry with a source URL, session, magnitude, surprise and gold labels; run the extraction test and the backtest.
- **Add an asset**: add loadings to every relevant channel, add it to `DEFAULT_ASSETS`, fetch its price history, and re-run the backtest.
- **Replace the analog model**: keep the walk-forward interface (`fit(prior_events, outcomes)`, `predict(event)`) and the no-look-ahead maturation rule.
- **Add a point-in-time macro source**: use FRED/ALFRED vintages and pass the analysis `as_of` through the pipeline; the audit will fail on look-ahead.
- **Rebuild the FOMC benchmark**: replace `backend/data/fomc/statements_2000_2025.csv` and run `python scripts/build_fomc_events.py`; then re-run `--dataset fomc`.
- **Add a surprise provider**: wire Fed-funds/SOFR futures or a consensus feed into `MacroEvent.surprise`; the FOMC benchmark is the acceptance test.
