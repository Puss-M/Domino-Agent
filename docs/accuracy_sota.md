# What "high accuracy" means in financial event prediction

This note answers a practical question: **how do other projects get high accuracy,
and what should Domino copy?** The short answer is uncomfortable: in daily
asset-direction prediction, credible state-of-the-art accuracy is roughly
**55–63%**, and many higher numbers come from leakage, an easier target, or a
simulation without costs. The useful goal is not "90% accuracy"; it is
**calibrated, cost-aware, out-of-sample skill**.

## Evidence from GitHub and papers (checked 2026-11-26)

| Source | Task / benchmark | Reported result | Method | Caveat |
|---|---|---|---|---|
| **PaCMoE** (Mathematics 2026; official code `EijiNagata-jpg/PaCMoE`) | ACL18/StockNet next-day direction, 3,666 test samples | **61.32% accuracy, MCC 0.2312** (seed 8); 10-seed range 58.8–61.3% | PatchTST price/technical encoders + FinBERT/FinGPT text + R-GCN correlation graph + pairwise cross-modal attention + mixture-of-experts | Strong protocol: chronological split, validation-MCC model selection, 10 seeds, walk-forward folds, 0/5/10/20bp transaction costs, deflated Sharpe, Fama–French/DCC baselines. This is the bar to copy. |
| **STST** (arXiv 2305.03835) | ACL18 / KDD17 direction | 63.71% / 56.88%; 31.24% annualized, 10.41pp above S&P | Spatiotemporal Transformer-LSTM | Abstract-level; no official code found in the GitHub sweep; simulation results need independent replication and costs. |
| **DTML** (KDD 2021; code `simonjisu/DTML-pytorch`) | Six market datasets | Up to 13.8pp higher profit than best competitors; 44.4% annualized in simulation | Data-axis Transformer + multi-level market contexts | Profit simulation, not accuracy; 35-star reimplementation, not the authors' production code. |
| **Qlib** (Microsoft, 50k stars) | Alpha158 / LightGBM, China A-share style | 17.83% annualized excess return **without cost**; 12.90% **with cost** | Gradient-boosted trees on engineered alpha factors | Different task (cross-sectional ranking), but the cost delta is the lesson: costs eat ~5pp. |
| **Audit-Ready ML** (2026, DOI via PaperDaily W7165023920) | Next-day signed return + volatility, US mega-caps, 2010–2026, 41 strictly causal folds | **Signed return: statistically indistinguishable from naive baselines across Ridge, RF, XGBoost, LightGBM, LSTM, CSTA, T-GAT**. Volatility: RF 7.19% RMSE reduction vs rolling baseline. | Fold-isolated preprocessing, expanding-window walk-forward, SHAP | The strongest warning: with causal folds and isolated preprocessing, direction alpha disappears; volatility/risk is the predictable target. |
| **The Wall Street Neophyte** (arXiv 2304.05351) | Zero-shot ChatGPT on multimodal stock movement | Underperforms SOTA **and linear regression on price features** | Prompting / CoT | LLM alone is not a high-accuracy direction model. |
| **Deep Limit Order Book Forecasting** (arXiv 2403.09267) | NASDAQ LOB mid-price | High forecasting power, but **not necessarily actionable trading signals** | Deep learning on LOB | Traditional ML metrics are inadequate for economic value. |
| **TradingAgents** (123k stars) | Multi-agent LLM trading framework | Claims improvements in cumulative return, Sharpe and max drawdown | Analyst/researcher/trader/risk agents with debate | High stars ≠ verified accuracy; README does not publish a reproducible accuracy table. |
| **FinGPT** (21k stars) | Financial sentiment / instruction tuning | Strong sentiment and instruction benchmarks | LoRA fine-tuning, open financial data | Not a direction predictor; sentiment accuracy is an easier target. |
| **FinRobot** (8.5k stars) | Equity research / valuation platform | No direction accuracy claim | Multi-agent CoT + tools + provenance | Architecture and workflow, not a benchmark result. |
| **Dexter** (28k stars) | Deep financial research agent | LLM-as-judge evaluation | Tool-using agent + LangSmith | Judge accuracy is not market accuracy. |

## What the high-accuracy projects actually do

### 1. They make the target easier or better defined

- **Cross-sectional ranking** (Qlib) instead of absolute up/down: predict which
  stocks beat which, then evaluate IC / RankIC and long-short returns.
- **Volatility / risk** instead of direction: Audit-Ready ML finds volatility is
  predictable even when direction is not.
- **5-day excess-return threshold** instead of raw next-day sign: fewer ties,
  less noise, but a different (easier) label.
- **Intraday / LOB** instead of daily macro: microstructure has more signal, but
  high forecasting power still may not survive costs.

### 2. They use multimodal data, not just news text

PaCMoE's recipe is the clearest:

- price/OHLCV + technical indicators (60-day window)
- financial text embeddings (FinBERT / FinGPT)
- a **daily correlation graph** built only from returns up to that day
- pairwise cross-modal attention + a mixture-of-experts router
- validation-MCC model selection, 10 seeds, walk-forward folds

The gain comes from **complementary modalities and a point-in-time graph**, not
from a better prompt.

### 3. They evaluate like a quant desk, not like a leaderboard

- chronological splits / expanding-window walk-forward
- **fold-isolated preprocessing** (no global normalization or feature selection)
- multiple seeds and mean ± dispersion
- MCC / IC / RankIC, not accuracy alone
- transaction costs (0/5/10/20bp), turnover, break-even cost
- deflated Sharpe ratio for multiple trials
- factor baselines (CAPM, Fama–French, DCC-GARCH)
- ablation of each modality

### 4. They use LLMs as perception or feature extractors, not as the predictor

- FinGPT: fine-tuned sentiment/instruction model, not a trading oracle.
- PaCMoE: FinBERT/FinGPT embeddings as text features.
- FinRobot/TradingAgents: LLM for research workflow and narration; performance
  claims are portfolio-level and need independent replication.
- Zero-shot ChatGPT direction prediction is explicitly a negative result.

## What this means for Domino

Domino's curated **60.4%** is already in the same range as credible ACL18 SOTA
(61.3%). The FOMC **41.1% vs 56.6% base** is not an embarrassment; it is the
same boundary the Audit-Ready ML paper finds: daily direction is hard, and naive
baselines are strong. The gap is not "we need a bigger LLM"; it is:

1. **A harder, larger, point-in-time benchmark** (more than 50 curated events;
   fold-isolated preprocessing; transaction costs).
2. **A cross-sectional target** (rank the 12 assets by expected CAR; evaluate
   IC/RankIC and a long-short portfolio) instead of 12 independent up/down
   classifications.
3. **Multimodal features**: event text + surprise + price/technical + cross-asset
   graph + intraday rates/FX. PaCMoE shows the gain is in fusion, not a single
   modality.
4. **A strong tabular baseline** (LightGBM/XGBoost on engineered features) before
   any deep model. Qlib's Alpha158 is a good template.
5. **Cost-aware evaluation**: net Sharpe, turnover, break-even cost, deflated
   Sharpe. A 1–2pp accuracy gain that dies at 5bp cost is not a gain.
6. **Calibration and abstention**: a 60% model that knows when it is uncertain is
   more useful than a 62% model that is confidently wrong.
7. **Regime conditioning**: the FOMC failure is a regime problem; add
   monetary/information/supply decomposition and regime features before adding
   capacity.

## A realistic "high accuracy" protocol for the next Domino experiment

| Step | Concrete choice | Acceptance criterion |
|---|---|---|
| Universe | 12 ETFs + 50–100 macro events per year, 2000–2026 | ≥ 500 event-asset observations |
| Target | Cross-sectional rank of CAR[0,+1]; secondary: up/down | Report IC, RankIC, long-short return, accuracy |
| Features | event type/direction/surprise + price/technical + cross-asset graph + rates/FX | Ablation per modality |
| Baselines | always-up, coin flip, Ridge, LightGBM/XGBoost | No deep model until it beats LightGBM |
| Model | LightGBM → Transformer/graph only if it adds | Validation MCC / IC |
| Split | expanding-window walk-forward, fold-isolated preprocessing | 5+ folds; no global fit |
| Costs | 0/5/10/20bp one-way; turnover; break-even | Net Sharpe and break-even cost |
| Uncertainty | event-clustered bootstrap; deflated Sharpe | 95% CI, multiple-testing adjustment |
| Calibration | Platt/isotonic; abstention threshold | ECE, coverage-accuracy curve |
| Reproducibility | seeds, config, data snapshot, one command | Clean-clone reproduction |

### E13 implemented (2026-11-26)

The protocol is now in [`cross_sectional.md`](cross_sectional.md) and
`backend/app/evaluation/cross_sectional.py`:

- 50 curated events, 600 rows, 5 expanding folds;
- LightGBM / ridge / momentum / random;
- target = within-event CAR rank; features strictly pre-event;
- gross and net long-short at 5/10/20bp.

Result: curated ridge +207.6bp gross (95% CI 41.5–418.2), but FOMC +2.2bp
(CI crosses zero), surprise-aware LightGBM +63.1bp (CI crosses zero), extended
momentum +66.2bp (CI crosses zero). **No model replicates across datasets**;
LightGBM overfits the 600-row panel. This is exactly the Audit-Ready ML lesson:
the direction edge is not robust, and the honest output is "no consistent edge".

## What not to chase

- **90% daily direction accuracy**: not credible without leakage, a different
  task, or intraday data with costs ignored.
- **More LLM agents / debate**: the evidence says homogeneous debate is not a
  verifier; FinVeriQA shows shared-evidence false confidence.
- **Single-number accuracy**: without base rate, class balance, costs and
  confidence interval, it is not interpretable.
- **Random train/test splits**: the fastest way to inflate accuracy in financial
  ML.
- **Global preprocessing**: normalization/feature selection before the split
  leaks the future; use fold-isolated preprocessing.
- **Simulation returns without costs**: Qlib's own example loses ~5pp annualized
  when costs are included.

## References

- PaCMoE, *Mathematics* 2026, 14(21), 3948; code `EijiNagata-jpg/PaCMoE`.
- STST, *Spatiotemporal Transformer for Stock Movement Prediction*, arXiv 2305.03835.
- DTML, *Accurate Multivariate Stock Movement Prediction via Data-Axis Transformer with Multi-Level Contexts*, KDD 2021; code `simonjisu/DTML-pytorch`.
- Qlib, `microsoft/qlib`, Alpha158/LightGBM benchmark.
- *Audit-Ready Machine Learning for Short-Horizon Equity Prediction*, 2026 (PaperDaily W7165023920).
- *The Wall Street Neophyte*, arXiv 2304.05351.
- *Deep Limit Order Book Forecasting*, arXiv 2403.09267.
- Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting* (2016).
- Domino internal: `docs/evaluation.md`, `docs/point_in_time.md`, `docs/paper_outline.md`.
