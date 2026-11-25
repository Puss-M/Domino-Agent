# Resume bullets and interview notes

## 中文版（建议 4 条，按“问题 → 做法 → 结果”写）

**Domino Agent — 事件驱动宏观传导与证据审计引擎**（个人项目，Python / FastAPI / 无前端构建）

- 将“LLM 生成因果链”的原型重构为五阶段事件驱动宏观传导引擎：金融文本抽取 → 带文献引用的机制检索 → 通道/资产传导图 → 证据审计 → 研究备忘录；沉淀 **20 条引用机制、14 个传导通道、50 个标注事件 + 58 个系统化 FOMC 事件、85 个测试**，无 API Key 可离线运行。
- 搭建数据与文本处理层：实现 SEC EDGAR/XBRL、GDELT、美国财政部、FRED/ALFRED、世界银行、Yahoo 六类连接器，统一缓存、重试、来源溯源与 point-in-time 说明；完成 **bps/pp/%/$tn/mb/d/中文单位归一、超预期与水平值区分、实体归一、LM 风格金融情感（否定/程度副词）与新闻近重复聚类**。
- 构建 walk-forward 事件研究：12 只 ETF、市场模型 CAR、盘后/周末事件日对齐、按事件聚类 bootstrap、配对 Brier 检验；样本外 **方向准确率 60.4% vs 53.8% 基线，Brier 0.238 vs 0.244，AUC 0.634，覆盖率 96.4%**；同时用 58 个系统化 FOMC 事件做压力测试，发现机制先验在“只看动作、没有 surprise”时显著为负技能（41.1% vs 56.6% 基线，ΔBrier +0.134，95% CI 0.076–0.180）。
- 设计证据约束与可审计性：每条图边绑定机制 ID 与文献引用，无匹配则弃权；审计检查引用完整性、证据等级、符号冲突与前视偏差；离线路径不调用 LLM，数字与图结构由确定性代码生成。

> 如果简历只能放一条：用第 3 条（有可验证的样本外指标），把第 1 条压缩成项目描述的第一句。

## English version

**Domino Agent — Event-driven macro transmission with an evidence audit** (personal project; Python / FastAPI / zero-build frontend)

- Rebuilt an LLM-only causal-chain prototype into a five-stage event-driven macro engine: finance-aware extraction → cited mechanism retrieval → channel/asset transmission graph → evidence audit → research memo. **20 cited mechanisms, 14 channels, 50 curated + 58 systematic FOMC events, 85 tests**; fully offline with no API key.
- Built the data and text layer: six provenance-aware connectors (SEC EDGAR/XBRL, GDELT, US Treasury, FRED/ALFRED, World Bank, Yahoo) with caching, retries and point-in-time notes; implemented **bps/pp/%/$tn/mb/d and Chinese unit normalization, surprise-vs-level separation, entity linking, LM-style financial sentiment with negation/intensifiers, and near-duplicate news clustering**.
- Built a walk-forward event study on 12 ETFs with market-model CARs, after-close/weekend alignment, event-clustered bootstrap and paired Brier tests: **60.4% accuracy vs 53.8% base rate, Brier 0.238 vs 0.244, AUC 0.634, 96.4% coverage** on the held-out curated half. Added a 58-event systematic FOMC stress test that exposes **negative skill without a surprise measure** (41.1% vs 56.6% base, ΔBrier +0.134, 95% CI 0.076–0.180).
- Designed evidence gating and auditability: every graph edge carries a mechanism ID and references; the engine abstains when no cited mechanism matches; the audit checks citation completeness, evidence grade, sign conflicts and look-ahead. The offline path is LLM-free — numbers and graph structure are deterministic.

## Interview talking points

### 1. “Why is this not just a prompt wrapper?”

Because the output is not generated prose. The event type, direction, magnitude, surprise, channel activations, asset signs and probabilities are produced by typed code from a cited library. The LLM is not on the offline path. If a reviewer deletes the frontend, the CLI still produces the same graph and memo. If a reviewer deletes the mechanism library, the engine abstains rather than hallucinating.

### 2. “What is the most important financial distinction you implemented?”

**Surprise vs level.** A 75bp hike is not a shock if the market priced 75bp. A CPI print of 8.6% is a level; 8.6% vs 8.3% expected is a +0.3pp surprise. The `Surprise` object carries value, unit, sign and the raw phrase, and the audit warns when a monetary/inflation event has no explicit surprise direction because the level may already be priced.

### 3. “Why one day and not five?”

Macro information is largely priced in the first session. The 1-day curated result is 60.4% accuracy / Brier 0.238 / AUC 0.634, with a 95% CI of 0.537–0.668. The 5-day robustness is 54.5% / 0.252 / 0.528. The project reports both; it does not claim a 5-day trading signal. The expected-CAR display is a 5-day order-of-magnitude prior, not the evaluation window.

### 4. “Why a market model instead of raw returns?”

Raw returns confound the event with market beta. A high-beta asset can fall on a risk-off day even if the event has no idiosyncratic effect. The market model estimates alpha and beta on `[-120, -21]` and computes CAR on the residual. SPY is the exception: its residual is zero by construction, so it is evaluated on its raw return.

### 5. “Why do you abstain? Doesn’t that hurt coverage?”

Coverage is 96.4% on the held-out half; the engine abstains when no cited mechanism matches or confidence is too low. A model that always answers looks better on coverage and worse on trust. The audit makes abstention visible instead of filling the gap with a plausible narrative.

### 6. “Is this causal inference?”

No. It is a cited transmission hypothesis plus an event-study test. It does not identify an ATE, does not control for confounders the way DoWhy/EconML would, and does not claim that the channel estimate is structural. The correct claim is: “on the 50-event curated sample the calibrated stack has a lower Brier than the base rate, but the accuracy improvement is not statistically significant; on the 58-event action-only FOMC stress test the mechanism prior is significantly worse than the base rate.” The FOMC failure is the most interesting result.

### 7. “What failed?”

- FOMC action-only events: mechanism 41.1% vs base 56.6%; ΔBrier +0.134, significant negative skill. The missing input is surprise/positioning.
- QQQ and XLU: the engine over-predicts duration-sensitive downside around hikes; growth rallied after several in-line hikes.
- FXI: two China events; the stimulus transmission is regime-dependent.
- Geopolitics: two events; the 1-day equity sign is noisy even when the safe-haven direction is right.
- 5-day horizon: the edge decays.
- Calibration middle bins: noisy with 33 predictions per bin and correlated assets within events.

### 8. “What would you do with more time/data?”

- Replace curated CPI/FOMC surprises with high-frequency Fed-funds/SOFR futures and a proper consensus feed.
- Use CRSP/Compustat or a vendor with point-in-time prices instead of Yahoo adjusted closes.
- Add high-yield OAS, breakevens, DXY, 2y/10y yields and Brent as conditioning variables, not just outcome assets.
- Expand the event sample and preregister the mechanism library before the test window.
- Add a proper execution model if the goal ever becomes P&L rather than evaluation.

### 9. “What did you borrow from other projects?”

Role separation from TradingAgents; “models reason, software computes, systems verify” and provenance from FinRobot; finance-specific sentiment and data pipelines from FinGPT; backtest discipline from AI Hedge Fund; multi-agent opinion analysis from BettaFish; the identification discipline (and the refusal to overclaim) from DoWhy/EconML.

### 10. “What is the one number you would put on a slide?”

**60.4% directional accuracy vs 53.8% base rate, Brier 0.238 vs 0.244, AUC 0.634, 96.4% coverage, 50 curated events, 1-day window, held-out half, 95% CI 0.537–0.668.** Then immediately say: the accuracy improvement is not statistically significant, the 5-day horizon is weaker, and the 58-event FOMC stress test is significantly worse than the base rate.

## What not to say

- “The model predicts markets.” It does not.
- “The graph is causal.” It is a cited transmission hypothesis.
- “100% extraction accuracy.” It is 50/50 on an in-sample curated vocabulary, not an OOD benchmark.
- “The backtest proves alpha.” There are no costs, no capacity, no point-in-time prices, and only 50 curated events.
- “SOTA prediction.” It is not. The defensible claim is SOTA-grade evaluation: two benchmarks, paired event-clustered tests, calibration, and a documented negative result.

## The SOTA framing to use

The project is **SOTA-grade in evaluation and evidence**, not in return prediction. The strongest sentence is:

> “I built an evidence-gated macro transmission engine and a 50+58+92-event benchmark suite. The curated stack reaches 60.4% directional accuracy (Brier 0.238, AUC 0.634), but the more interesting result is the systematic FOMC stress test: without a surprise/positioning measure, the mechanism prior is significantly worse than a base rate. That is why the next step is high-frequency Fed-funds data, not another prompt.”

That sentence is honest, specific, and hard to fake. It is better than a cherry-picked accuracy number.
