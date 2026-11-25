"""Policy-as-code compliance layer and hash-chained audit ledger.

Policies are executable constraints over the final `AnalysisResponse`, not
prompt instructions. A failed policy names the rule and the offending field,
so the audit trail is actionable. P-004 is the anti-hallucination contract: a
narrator (LLM or template) may only use numbers that the deterministic engine
already produced.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings, get_settings
from ..schemas import AnalysisResponse, PolicyResult, SymbolicReport

ADVICE_RE = re.compile(
    r"\b(you should|we recommend|buy now|sell now|go long|go short|"
    r"建议买入|建议卖出|应当买入|应当卖出|推荐买入|推荐卖出)\b",
    re.IGNORECASE,
)
MECHANISM_ID_RE = re.compile(
    r"\b(?:MON|INFL|LABOR|TRADE|OIL|GEO|CHINA|FISCAL|BANK|BOJ|ECB)_[A-Z0-9_]{2,}\b"
)
ASSET_RE = re.compile(r"\b(?:SPY|QQQ|TLT|IEF|UUP|GLD|XLE|XLU|EEM|HYG|FXI|VIX)\b")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")


@dataclass
class Policy:
    id: str
    title: str
    severity: str
    checker: object

    def evaluate(
        self,
        response: AnalysisResponse,
        symbolic: SymbolicReport | None,
        knowledge=None,
    ) -> PolicyResult:
        if self.id == "P-011":
            passed, detail = self.checker(response, symbolic, knowledge)
        else:
            passed, detail = self.checker(response, symbolic)
        return PolicyResult(
            id=self.id,
            title=self.title,
            passed=bool(passed),
            severity=self.severity,
            detail=detail,
        )


def _visible_text(response: AnalysisResponse) -> str:
    return " ".join(
        [
            response.memo.summary,
            " ".join(response.memo.asset_views),
            " ".join(response.memo.transmission),
        ]
    )


def _allowed_numbers(response: AnalysisResponse) -> set[float]:
    allowed: set[float] = set()
    event = response.event
    if event.magnitude:
        allowed.add(float(event.magnitude.value))
    if event.surprise:
        allowed.add(float(event.surprise.value))
    allowed.add(float(event.confidence))
    for prediction in response.predictions:
        allowed.update(
            {
                float(prediction.p_up),
                float(prediction.expected_car_bps),
                float(prediction.confidence),
                float(prediction.horizon_days),
            }
        )
    for activation in response.channel_activations:
        allowed.add(float(activation.score))
    # Numbers already present in the event text are facts, not model claims.
    for text in (event.headline, event.summary):
        for match in NUMBER_RE.findall(text):
            allowed.add(float(match))
    return allowed


def _p001(response, _symbolic):
    ok = "not investment advice" in response.memo.disclaimer.lower()
    return ok, "Memo must state that it is not investment advice."


def _p002(response, _symbolic):
    match = ADVICE_RE.search(_visible_text(response))
    if match:
        return False, f"Advice language found: {match.group(0)!r}"
    return True, "No advice language in visible output."


def _p003(response, _symbolic):
    missing = [
        prediction.asset
        for prediction in response.predictions
        if not prediction.abstain and not prediction.mechanisms
    ]
    return (not missing, f"Predictions without a mechanism: {missing}" if missing else "OK")


def _p004(response, _symbolic):
    allowed = _allowed_numbers(response)
    orphans: list[str] = []
    for number in NUMBER_RE.findall(response.memo.summary):
        value = float(number)
        if YEAR_RE.match(number):
            continue
        if any(abs(value - candidate) <= 0.51 for candidate in allowed):
            continue
        orphans.append(number)
    if orphans:
        return False, f"Untraceable numbers in memo: {sorted(set(orphans))}"
    return True, "Every number in the summary is traceable to the structured result."


def _p005(response, _symbolic):
    leak = [
        prediction.asset
        for prediction in response.predictions
        if not prediction.abstain and prediction.confidence < 0.15
    ]
    return (not leak, f"Low-confidence non-abstain: {leak}" if leak else "OK")


def _p006(response, _symbolic):
    return response.audit.passed, "; ".join(response.audit.issues) or "Deterministic audit passed."


def _p007(response, _symbolic):
    event = response.event
    surprise_missing = event.event_type.value == "monetary_policy" and (
        event.surprise is None or event.surprise.sign == "neutral"
    )
    if not surprise_missing:
        return True, "n/a (surprise quantified)"
    warnings = " ".join(response.audit.warnings).lower()
    ok = "priced" in warnings or "surprise" in warnings
    return ok, "Action-only monetary event must warn that the level may already be priced."


def _p008(response, symbolic):
    if symbolic is None:
        return True, "No symbolic report attached."
    bad = [
        proof.asset
        for proof in symbolic.proofs
        if proof.status == "not_entailed"
        and any(p.asset == proof.asset and not p.abstain for p in response.predictions)
    ]
    if bad:
        return False, f"Numeric prediction has a formally unentailed direction: {bad}"
    return True, "No numeric prediction contradicts a formal proof."


def _p009(response, symbolic):
    if symbolic is None:
        return True, "No symbolic report attached."
    ambiguous = [proof.asset for proof in symbolic.proofs if proof.status == "ambiguous"]
    if ambiguous:
        return False, f"Symbolic direction is ambiguous for: {ambiguous}"
    return True, "Every active asset has a definite symbolic direction."


def _used_mechanism_ids(response: AnalysisResponse) -> set[str]:
    used: set[str] = set()
    for prediction in response.predictions:
        used.update(prediction.mechanisms)
    return used


def _p010(response, _symbolic):
    used = _used_mechanism_ids(response)
    text = _visible_text(response)
    mentioned = set(MECHANISM_ID_RE.findall(text))
    fabricated = sorted(mentioned - used)
    if fabricated:
        return False, f"Narrative cites mechanisms that were not used: {fabricated}"
    return True, "Every mechanism ID in the narrative was actually used."


def _p011(response, _symbolic, knowledge=None):
    if knowledge is None:
        return True, "Knowledge base not attached to policy engine; citation check skipped."
    used = _used_mechanism_ids(response)
    allowed: set[str] = set()
    for mechanism in knowledge.mechanisms:
        if mechanism.id in used:
            allowed.update(mechanism.citations)
    fabricated = sorted(set(response.memo.citations) - allowed)
    if fabricated:
        return False, f"Memo cites sources not attached to a used mechanism: {fabricated}"
    return True, "Every memo citation belongs to a used mechanism."


def _p012(response, _symbolic):
    allowed = {prediction.asset for prediction in response.predictions}
    mentioned: set[str] = set()
    for line in response.memo.asset_views:
        token = line.strip().split(":", 1)[0].split()[0].strip("(),")
        if re.fullmatch(r"[A-Z^][A-Z0-9^]{1,6}", token):
            mentioned.add(token)
    fabricated = sorted(mentioned - allowed)
    if fabricated:
        return False, f"Narrative mentions assets outside the prediction universe: {fabricated}"
    return True, "Every asset mentioned in the memo is in the prediction universe."


DEFAULT_POLICIES = [
    Policy("P-001", "Disclaimer present", "error", _p001),
    Policy("P-002", "No investment advice", "error", _p002),
    Policy("P-003", "Every prediction cites a mechanism", "error", _p003),
    Policy("P-004", "Narrative numbers are grounded", "error", _p004),
    Policy("P-005", "Low-confidence predictions abstain", "error", _p005),
    Policy("P-006", "Deterministic audit passes", "error", _p006),
    Policy("P-007", "Action-only monetary events warn", "warning", _p007),
    Policy("P-008", "Numeric direction does not contradict a proof", "error", _p008),
    Policy("P-009", "Symbolic ambiguity is surfaced", "warning", _p009),
    Policy("P-010", "Narrative mechanism IDs are grounded", "error", _p010),
    Policy("P-011", "Narrative citations are grounded", "error", _p011),
    Policy("P-012", "Narrative assets are grounded", "error", _p012),
]


class PolicyEngine:
    def __init__(self, policies: list[Policy] | None = None, knowledge=None):
        self.policies = policies or DEFAULT_POLICIES
        self.knowledge = knowledge

    def evaluate(
        self, response: AnalysisResponse, symbolic: SymbolicReport | None
    ) -> list[PolicyResult]:
        return [policy.evaluate(response, symbolic, self.knowledge) for policy in self.policies]

    @staticmethod
    def failed(results: list[PolicyResult]) -> list[PolicyResult]:
        return [result for result in results if not result.passed]


class AuditLedger:
    """Append-only hash chain: each record commits to the previous record."""

    def __init__(self, settings: Settings | None = None, path: Path | None = None):
        settings = settings or get_settings()
        self.path = path or (settings.cache_dir / "audit" / "ledger.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        last = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = line
        if not last:
            return "GENESIS"
        try:
            return json.loads(last)["hash"]
        except (json.JSONDecodeError, KeyError):
            return "GENESIS"

    def append(self, payload: dict) -> dict:
        previous = self._last_hash()
        seq = 1
        if self.path.exists():
            seq = sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()) + 1
        body = {
            "seq": seq,
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "prev_hash": previous,
            "payload": payload,
        }
        canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        record = {**body, "hash": digest}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record

    def verify_chain(self) -> bool:
        if not self.path.exists():
            return True
        previous = "GENESIS"
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("prev_hash") != previous:
                return False
            body = {
                "seq": record["seq"],
                "recorded_at": record["recorded_at"],
                "prev_hash": record["prev_hash"],
                "payload": record["payload"],
            }
            canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
            expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if expected != record.get("hash"):
                return False
            previous = record["hash"]
        return True
