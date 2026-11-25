# Neuro-symbolic layer

This document describes the v0.4 symbolic kernel: what it formalizes, what it proves, and what it explicitly cannot prove.

## Why a symbolic layer

The 2026 literature is unusually clear about the limits of "more agents":

- **More Debate, Same Evidence** (arXiv 2608.00243): a homogeneous three-agent debate panel changes groundedness accuracy by +8.5 to −4.4 percentage points across six benchmarks; three are statistically inconclusive. Debate alone is not a reliable verifier.
- **The Hallucination Snowball** (arXiv 2608.14588): in sequential multi-agent pipelines, a Stage-1 numeric error becomes a derived computation, then prose, then an editorially approved conclusion. Per-boundary escape probabilities are 24.6%, 48.3% and 89.3%; detectability degrades at every handoff.
- **Delayed Verification Destabilizes Multi-Agent LLM Belief** (arXiv 2606.27409): verification delay can turn consensus into oscillation; corrector placement matters.
- **FormaFin** (arXiv 2611.28881) and **SOVER** (arXiv 2609.00728) move the verification into an SMT solver rather than another LLM.
- **Beyond LLM Wrappers** (arXiv 2610.39230) describes a production-grounded "three-engine" architecture: a financial knowledge graph, a deterministic compute engine, and an LLM layer for intent/orchestration/narration.

Domino's v0.4 follows the same principle: **LLMs, if used at all, are perception and narration. The numbers, signs, proofs and compliance checks are deterministic.**

```
optional LLM perception          symbolic kernel (mandatory)          compliance
────────────────────────         ───────────────────────────          ──────────
schema-constrained extraction -> typed event + dimension check   ->   P-001..P-009
claim / belief-object parsing -> sign algebra over influence graph ->  numeric grounding
narration (no arithmetic)     -> SMT proof cores / ambiguity     ->   hash-chained ledger
```

## 1. Sign algebra

A qualitative sign is one of `+`, `-`, `0`, `?`.

- **Serial composition** (event → channel → asset) is multiplication:
  `+ × + = +`, `+ × - = -`, `- × - = +`, `0` absorbs, `?` propagates.
- **Parallel composition** (several mechanisms on the same edge, or several paths to the same asset) is qualitative addition:
  all `+` → `+`; all `-` → `-`; mixed → `?`.

For a hawkish policy shock, the graph has 19 nodes and 78 edges. QQQ/SPY/EEM/HYG/FXI are **proved** negative. TLT, IEF, GLD and XLU are **ambiguous**: the real-yield/nominal-yield path is negative, while the risk-premium/credit-spread/safe-haven path is positive. The numeric model nets these to −119bp for TLT; the symbolic layer refuses to hide the conflict.

That refusal is the point. A confidence score can be high while the sign is genuinely unidentified; the symbolic layer makes the conflict explicit and names the mechanisms on each side.

## 2. SMT certification

The sign algebra answers "what follows from all cited mechanisms". The SMT layer answers "**which minimal set of mechanisms is sufficient to entail the direction, and is the claim consistent at all?**"

Encoding (`backend/app/symbolic/smt.py`):

1. One Boolean activation variable per matched mechanism.
2. Each edge's sign is the sign of the active weighted sum (`>0`, `<0`, `=0`).
3. Each path's sign is the qualitative product of its edge signs; enumerated over `3^L` assignments (L ≤ 4).
4. An asset is definitely positive if some path is positive and no path is negative (and analogously for negative).
5. `z3.Optimize` minimizes the number of active mechanisms subject to the claim. The resulting active set is a **minimal proof core**.

Proof statuses:

| Status | Meaning |
|---|---|
| `proved` | A minimal mechanism set entails the direction; the core is returned |
| `ambiguous` | Both directions are consistent with the cited paths |
| `not_entailed` | The cited paths do not entail the direction |
| `unverified` | Solver unavailable or the claim is non-directional |

The proof core is machine-checkable: it names the exact mechanisms that carry the claim. A reviewer can challenge one mechanism and see whether the proof survives.

## 3. Ambiguity is a first-class output

The UI shows a proof badge per asset and a "Symbolic verification" panel listing every ambiguous asset with the number of positive/negative paths and the explanation. The audit policy `P-009` raises a warning when ambiguity exists; `P-008` raises an **error** only when a numeric prediction contradicts a formal proof (`not_entailed`).

This is intentionally different from "the model is 0.83 confident". Confidence is a numeric summary; ambiguity is a structural fact.

## 4. Policy-as-code

Policies are executable predicates over the final response, not prompt instructions:

| ID | Severity | Check |
|---|---|---|
| P-001 | error | Disclaimer present |
| P-002 | error | No advice language (EN/ZH) |
| P-003 | error | Every non-abstain prediction cites a mechanism |
| **P-004** | error | **Every number in the summary is traceable to the structured result** |
| P-005 | error | Low-confidence predictions abstain |
| P-006 | error | Deterministic audit passes |
| P-007 | warning | Action-only monetary events warn that the level may be priced |
| P-008 | error | No numeric prediction contradicts a formal proof |
| P-009 | warning | Symbolic ambiguity is surfaced |

P-004 is the anti-hallucination contract for any future LLM narrator: an injected memo claiming "SPY will fall 3.2%, gold +12.5%, 95.7% confident, we recommend you buy gold" fails P-002 and P-004. This is verified in `tests/test_symbolic.py`.

The audit ledger (`backend/app/symbolic/policy.py`) appends a hash-chained record for every analysis: `hash = SHA256(seq, timestamp, prev_hash, payload)`. The response carries the record hash; `verify_chain()` recomputes the chain. It is a minimal compliance artifact: every published analysis is committed to an append-only log.

## 5. Typed ontology

`backend/app/symbolic/ontology.py` gives units dimensions (`bps`/`pp` → rate, `pct` → inflation level, `usd_bn` → money, `mbpd`/`count` → quantity) and checks that an event's magnitude dimension is compatible with its type. It also exports the mechanism library as RDF/Turtle at `GET /api/ontology.ttl`, with channels, loadings, evidence grades, and `dct:source` citations.

## 6. What this does not do

- It does **not** identify a structural causal effect. A proof is relative to the cited mechanism library, not to the world.
- It does **not** resolve sign ambiguity. TLT is genuinely ambiguous under a hawkish shock until a regime condition or data decides. The FOMC stress test shows what happens when you pretend otherwise.
- It does **not** fix the FOMC failure. The missing input is high-frequency Fed-funds/SOFR pricing or staff-expectation data (Bauer & Swanson 2023; Nakamura & Steinsson 2013), not a better symbolic encoding.
- It does **not** let the LLM produce numbers. If a narrator is added, P-004 remains the gate.

## 7. How to extend

- Add a **regime condition** to a mechanism (e.g., `requires: risk_premium > 0`) and encode it as an SMT assumption; ambiguity then becomes conditional rather than unconditional.
- Add **belief objects** (inflation, growth, financial conditions, credibility) and a narrative-baseline delta, following *Changing the Narrative* (SSRN 6677954).
- Add a **high-frequency surprise adapter** and use it to replace the neutral `Surprise` in the FOMC benchmark.
- Add a **Kolari–Pynnönen** cross-correlation-adjusted test as a robustness check for the event study.


## 8. What the field has converged on (2026 evidence)

The best systems no longer rely on "another LLM reviews it". The convergent pattern is:

| Mechanism | Evidence / system | How Domino implements it |
|---|---|---|
| Deterministic compute separated from narration | FinRobot V2: 32 pure-Python operators, provenance-tracked artifacts, output-contract gate | Numeric transmission + sign algebra + SMT are deterministic; a narrator may only narrate |
| Backtest / execution as the verifier | RD-Agent(Q): LLM proposes, Docker backtest disposes | Event-study evaluation is the final arbiter; no LLM in the metric path |
| Policy compiled to executable code | GuardAgent (ICML 2025): natural-language policy → code, deterministic enforcement | P-001..P-009 are predicates over the response, not prompts |
| Deterministic rails at tool boundaries | NeMo Guardrails IORails: regex/CEL rules at input/output/tool call/tool result | P-004 numeric grounding plus the hash-chained ledger |
| Tamper-evident session ledger | ai-hedge-fund paper-trading: hash-chained ledger, approval gates | `AuditLedger` hash chain in `symbolic/policy.py` |
| Structured output contracts | OpenAI CFG decoding: 100% schema conformance vs 93% fine-tuned and <40% prompting-only | Pydantic contracts + rule-first extraction; optional LLM must emit schema-valid JSON |
| Adversarial coverage, not consensus | Tool-MAD; PROClaim; *More Debate, Same Evidence* (arXiv 2608.00243) | The "critic" role is the symbolic auditor, not a second opinion |
| Temporal integrity | *The Alpha Illusion* P1–P6 protocol; blind backtests with t-0/t-1 labels | Walk-forward splits, matured analogs, revised-price caveat, no look-ahead audit |

What does **not** work as a verification strategy: homogeneous debate. The 2026 evidence is consistent: *The Cost of Consensus* (arXiv 2605.00914) reports sycophantic conformity up to 85.5% and destabilization of previously correct reasoning up to 70%; *More Debate, Same Evidence* finds +8.5 to −4.4pp across six groundedness benchmarks; *The Hallucination Snowball* shows errors becoming invisible across sequential handoffs. Domino's answer is to put the reliability budget into the symbolic gates, not into more agents.

## 9. Compliance mapping (why this matters to a regulated user)

The policies are not generic "AI safety" fluff; they map onto obligations a financial institution already has:

| Policy / artifact | Regulatory analogue |
|---|---|
| P-001 disclaimer, P-002 no advice | SEC Marketing Rule; MiFID II suitability/communications; "not investment advice" |
| P-003 evidence, P-004 grounded numbers | SEC "AI washing" enforcement (Press Release 2024-36): performance/capability claims must be substantiated; provenance |
| P-006 audit, P-008 proof consistency | Fed SR 11-7 model risk management: independent validation and effective challenge |
| P-005 abstention | Risk controls; human oversight (EU AI Act high-risk obligations) |
| P-009 ambiguity warning | Model limitations disclosure; SR 11-7 documentation |
| Hash-chained ledger | SR 11-7 documentation; EU AI Act logging; FINRA 3110 supervisory records |

This is a design sketch, not legal advice. A production deployment needs counsel, a formal model inventory, and independent validation. But the architecture is pointed in the right direction: every output has a policy result, a proof status, and a ledger hash.

## 10. References

- FormaFin, arXiv 2611.28881 (2026).
- SOVER, arXiv 2609.00728 (2026).
- *Beyond LLM Wrappers: Context Engineering and the Three-Engine Architecture for Reliable Financial AI*, arXiv 2610.39230 (2026).
- *More Debate, Same Evidence: Structural Limits of Homogeneous Multi-Agent Groundedness*, arXiv 2608.00243 (2026).
- *The Hallucination Snowball*, arXiv 2608.14588 (2026).
- *Delayed Verification Destabilizes Multi-Agent LLM Belief*, arXiv 2606.27409 (2026).
- *The Cost of Consensus*, arXiv 2605.00914 (2026).
- *The Alpha Illusion*, arXiv 2605.16895 (2026).
- FinRobot V2, AI4Finance; RD-Agent(Q), Microsoft Research; GuardAgent, ICML 2025; NeMo Guardrails; ai-hedge-fund.
- Bauer & Swanson, NBER Macroeconomics Annual 2023; Nakamura & Steinsson, QJE 2013.
- Kolari & Pynnönen, RFS 2010.
- *Changing the Narrative*, SSRN 6677954 (2026); *Identifying Monetary Policy Shocks with LLMs*, SSRN 7560498 (2026).
