# Resume bullets and interview notes

## 中文版（建议 4 条，按“问题 → 做法 → 结果”写）

**Domino Agent — 事件驱动宏观传导与证据审计引擎**（个人项目，Python / FastAPI / 无前端构建）

- 将“LLM 生成因果链”的原型重构为六阶段事件驱动宏观传导引擎（增加符号验证层）：金融文本抽取 → 带文献引用的机制检索 → 通道/资产传导图 → 证据审计 → 研究备忘录；沉淀 **20 条引用机制、14 个传导通道、50 个标注事件 + 58 个系统化 FOMC 事件 + 45 个 surprise-aware 事件、113 个测试**，无 API Key 可离线运行。
- 搭建数据与文本处理层：实现 SEC EDGAR/XBRL、GDELT、美国财政部、FRED/ALFRED、世界银行、Yahoo 六类连接器，统一缓存、重试、来源溯源与 point-in-time 说明；完成 **bps/pp/%/$tn/mb/d/中文单位归一、超预期与水平值区分、实体归一、LM 风格金融情感（否定/程度副词）与新闻近重复聚类**。
- 构建 walk-forward 事件研究：12 只 ETF、市场模型 CAR、盘后/周末事件日对齐、按事件聚类 bootstrap、配对 Brier 检验；样本外 **方向准确率 60.4% vs 53.8% 基线，Brier 0.238 vs 0.244，AUC 0.634，覆盖率 96.4%**；同时用 58 个系统化 FOMC 事件做压力测试，发现机制先验在“只看动作、没有 surprise”时显著为负技能（41.1% vs 56.6% 基线，ΔBrier +0.134，95% CI 0.076–0.180）。
- 设计证据约束与可审计性：每条图边绑定机制 ID 与文献引用，无匹配则弃权；审计检查引用完整性、证据等级、符号冲突与前视偏差；离线路径不调用 LLM，数字与图结构由确定性代码生成。
- 引入神经符号内核：把机制库编译为带符号影响图，用定性符号代数组合路径，用 **Z3 求最小证明核（proof core）**，把“歧义”作为一等输出；配合 **P-001–P-013 合规即代码** 与 **SHA-256 哈希链审计账本**。注入“SPY 跌 3.2%、黄金涨 12.5%、建议买入”的幻觉 memo 会被 P-002/P-004 直接拦截；规模化审计 60/60 命中、10 条干净输出 0 误报。
- 做符号层消融与时间完整性审计：E6 证明符号层**不提升**方向准确率（blend ΔBrier −0.0002, p=0.52），价值在歧义披露与可审计性；E11 用机器可读 point-in-time contract 标注所有基准 `not_point_in_time`，区分参数化前视与数据修订泄漏。113 个测试，CI 全绿。

> 如果简历只能放一条：用第 3 条（有可验证的样本外指标），把第 1 条压缩成项目描述的第一句。

## English version

**Domino Agent — Event-driven macro transmission with an evidence audit** (personal project; Python / FastAPI / zero-build frontend)

- Rebuilt an LLM-only causal-chain prototype into a six-stage event-driven macro engine (with a symbolic verification layer): finance-aware extraction → cited mechanism retrieval → channel/asset transmission graph → evidence audit → research memo. **20 cited mechanisms, 14 channels, 50 curated + 58 systematic FOMC + 45 surprise-aware events, 113 tests**; fully offline with no API key.
- Built the data and text layer: six provenance-aware connectors (SEC EDGAR/XBRL, GDELT, US Treasury, FRED/ALFRED, World Bank, Yahoo) with caching, retries and point-in-time notes; implemented **bps/pp/%/$tn/mb/d and Chinese unit normalization, surprise-vs-level separation, entity linking, LM-style financial sentiment with negation/intensifiers, and near-duplicate news clustering**.
- Built a walk-forward event study on 12 ETFs with market-model CARs, after-close/weekend alignment, event-clustered bootstrap and paired Brier tests: **60.4% accuracy vs 53.8% base rate, Brier 0.238 vs 0.244, AUC 0.634, 96.4% coverage** on the held-out curated half. Added a 58-event systematic FOMC stress test that exposes **negative skill without a surprise measure** (41.1% vs 56.6% base, ΔBrier +0.134, 95% CI 0.076–0.180).
- Designed evidence gating and auditability: every graph edge carries a mechanism ID and references; the engine abstains when no cited mechanism matches; the audit checks citation completeness, evidence grade, sign conflicts and look-ahead. The offline path is LLM-free — numbers and graph structure are deterministic.
- Added a neuro-symbolic kernel: the mechanism library compiles into a signed influence graph; qualitative sign algebra composes paths; **Z3 returns a minimal proof core** or an explicit **ambiguity** status; **P-001–P-013 policy-as-code** enforces disclaimer, no-advice, numeric and unit grounding, abstention, proof consistency and mechanism/citation/asset grounding; every analysis is committed to a **SHA-256 hash-chained audit ledger**. An injected hallucinated memo ("SPY −3.2%, gold +12.5%, we recommend buying gold") is blocked by P-002/P-004 in the test suite.
- Ran the symbolic ablation and temporal-integrity audit: E6 shows the symbolic layer does **not** improve directional accuracy (blend ΔBrier −0.0002, p=0.52); its value is ambiguity disclosure and auditability. E11 adds a machine-readable point-in-time contract that labels every benchmark `not_point_in_time`, separating parametric lookahead from data-revision leakage. **113 tests**, CI green.

## Interview talking points

### 1. “Why not just add another reviewer agent?”

Because the 2026 evidence says that does not work reliably. *More Debate, Same Evidence* (arXiv 2608.00243) finds homogeneous panels change groundedness by +8.5 to −4.4pp, with three of six benchmarks inconclusive; *The Hallucination Snowball* (arXiv 2608.14588) shows errors becoming invisible across sequential handoffs. Domino's reviewer is a deterministic audit plus sign algebra plus Z3 plus executable policies. The proof core names the exact mechanisms; the ledger makes the output tamper-evident.

### 2. “Why is this not just a prompt wrapper?”

Because the output is not generated prose. The event type, direction, magnitude, surprise, channel activations, asset signs and probabilities are produced by typed code from a cited library. The LLM is not on the offline path. If a reviewer deletes the frontend, the CLI still produces the same graph and memo. If a reviewer deletes the mechanism library, the engine abstains rather than hallucinating.

### 3. “What is the most important financial distinction you implemented?”

**Surprise vs level.** A 75bp hike is not a shock if the market priced 75bp. A CPI print of 8.6% is a level; 8.6% vs 8.3% expected is a +0.3pp surprise. The `Surprise` object carries value, unit, sign and the raw phrase, and the audit warns when a monetary/inflation event has no explicit surprise direction because the level may already be priced.

### 4. “Why one day and not five?”

Macro information is largely priced in the first session. The 1-day curated result is 60.4% accuracy / Brier 0.238 / AUC 0.634, with a 95% CI of 0.537–0.668. The 5-day robustness is 54.5% / 0.252 / 0.528. The project reports both; it does not claim a 5-day trading signal. The expected-CAR display is a 5-day order-of-magnitude prior, not the evaluation window.

### 5. “Why a market model instead of raw returns?”

Raw returns confound the event with market beta. A high-beta asset can fall on a risk-off day even if the event has no idiosyncratic effect. The market model estimates alpha and beta on `[-120, -21]` and computes CAR on the residual. SPY is the exception: its residual is zero by construction, so it is evaluated on its raw return.

### 6. “Why do you abstain? Doesn’t that hurt coverage?”

Coverage is 96.4% on the held-out half; the engine abstains when no cited mechanism matches or confidence is too low. A model that always answers looks better on coverage and worse on trust. The audit makes abstention visible instead of filling the gap with a plausible narrative.

### 7. “Is this causal inference?”

No. It is a cited transmission hypothesis plus an event-study test. It does not identify an ATE, does not control for confounders the way DoWhy/EconML would, and does not claim that the channel estimate is structural. The correct claim is: “on the 50-event curated sample the calibrated stack has a lower Brier than the base rate, but the accuracy improvement is not statistically significant; on the 58-event action-only FOMC stress test the mechanism prior is significantly worse than the base rate.” The FOMC failure is the most interesting result.

### 8. “What failed?”

- FOMC action-only events: mechanism 41.1% vs base 56.6%; ΔBrier +0.134, significant negative skill.
- FOMC surprise-aware events: even with the BRW (2021) daily surprise, mechanism 45.3% vs base 52.7%; tightening 52.2%, easing 43.3%. The missing input is the monetary/information decomposition, not just a surprise number.
- QQQ and XLU: the engine over-predicts duration-sensitive downside around hikes; growth rallied after several in-line hikes.
- FXI: two China events; the stimulus transmission is regime-dependent.
- Geopolitics: two events; the 1-day equity sign is noisy even when the safe-haven direction is right.
- 5-day horizon: the edge decays.
- Calibration middle bins: noisy with 33 predictions per bin and correlated assets within events.

### 9. “What would you do with more time/data?”

- Replace curated CPI/FOMC surprises with high-frequency Fed-funds/SOFR futures and a proper consensus feed.
- Add the Jarociński–Karadi (2020) monetary/information decomposition or an intraday rate-equity co-movement proxy; the BRW surprise-aware test shows a surprise number alone is not enough.
- Use CRSP/Compustat or a vendor with point-in-time prices instead of Yahoo adjusted closes.
- Add high-yield OAS, breakevens, DXY, 2y/10y yields and Brent as conditioning variables, not just outcome assets.
- Expand the event sample and preregister the mechanism library before the test window.
- Add a proper execution model if the goal ever becomes P&L rather than evaluation.

### 10. “What did you borrow from other projects?”

Role separation from TradingAgents; “models reason, software computes, systems verify” and provenance from FinRobot; finance-specific sentiment and data pipelines from FinGPT; backtest discipline from AI Hedge Fund; multi-agent opinion analysis from BettaFish; the identification discipline (and the refusal to overclaim) from DoWhy/EconML.

### 11. “What is the one number you would put on a slide?”

**60.4% directional accuracy vs 53.8% base rate, Brier 0.238 vs 0.244, AUC 0.634, 96.4% coverage, 50 curated events, 1-day window, held-out half, 95% CI 0.537–0.668.** Then immediately say: the accuracy improvement is not statistically significant, the 5-day horizon is weaker, and the 58-event FOMC stress test is significantly worse than the base rate.

## What not to say

- “The model predicts markets.” It does not.
- “The graph is causal.” It is a cited transmission hypothesis.
- “100% extraction accuracy.” It is 50/50 on an in-sample curated vocabulary, not an OOD benchmark.
- “The backtest proves alpha.” There are no costs, no capacity, no point-in-time prices, and only 50 curated events.
- “SOTA prediction.” It is not. The defensible claim is SOTA-grade **evaluation and verification**: two benchmarks, paired event-clustered tests, calibration, a documented negative result, and a neuro-symbolic verification layer with formal proof cores and policy-as-code compliance.

## The SOTA framing to use

The project is **SOTA-grade in evaluation and verification**, not in return prediction. The strongest sentence is:

> “I built a neuro-symbolic macro transmission engine: a cited mechanism library compiles into a signed influence graph, qualitative sign algebra and Z3 return a minimal proof core or an explicit ambiguity status, and a policy-as-code layer enforces numeric grounding, no-advice and a hash-chained audit ledger. On a 50+58+92-event benchmark the curated stack reaches 60.4% directional accuracy (Brier 0.238, AUC 0.634), but the more interesting result is the systematic FOMC stress test: without a surprise/positioning measure, the mechanism prior is significantly worse than a base rate. The 2026 literature shows homogeneous multi-agent debate is not a reliable verifier (*More Debate, Same Evidence*; *The Hallucination Snowball*), so the next step is symbolic verification plus high-frequency Fed-funds data, not another prompt.”

That sentence is honest, specific, and hard to fake. It is better than a cherry-picked accuracy number.
