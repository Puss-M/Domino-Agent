"""Evidence retrieval over the transmission library.

This is retrieval-augmented generation without the generation: the event is
matched against a small, cited mechanism library, and the retrieved mechanisms
are the only ones the downstream graph is allowed to use.
"""

from __future__ import annotations

import re

from ..schemas import EvidenceGrade, MacroEvent, MechanismMatch
from .loader import KnowledgeBase


def _contains(text: str, term: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", term):
        return term in text
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text))


class MechanismRetriever:
    def __init__(self, knowledge: KnowledgeBase):
        self.knowledge = knowledge

    def match(self, event: MacroEvent, include_speculative: bool = False) -> list[MechanismMatch]:
        text = f"{event.headline} {event.summary} {' '.join(event.keywords)}".lower()
        candidates: list[MechanismMatch] = []
        for mechanism in self.knowledge.mechanisms:
            if event.event_type not in mechanism.event_types:
                continue
            if mechanism.directions and event.direction not in mechanism.directions:
                continue
            if mechanism.actors and (event.actor is None or event.actor not in mechanism.actors):
                continue
            if mechanism.evidence_grade == EvidenceGrade.D and not include_speculative:
                continue

            if mechanism.any_keywords:
                matched_conditions = [kw for kw in mechanism.any_keywords if _contains(text, kw)]
                if not matched_conditions:
                    continue
            else:
                matched_conditions = []
            matched_none = [kw for kw in mechanism.none_keywords if _contains(text, kw)]
            if matched_none:
                continue

            score = mechanism.confidence
            if mechanism.actors:
                score += 0.1
            if matched_conditions:
                score += 0.06 * min(len(matched_conditions), 3)
            # A small bonus for lexical overlap with the mechanism title/rationale
            # keeps the ranking sensible when several mechanisms share a trigger.
            title_terms = set(re.findall(r"[a-z]{4,}", mechanism.title.lower()))
            overlap = [term for term in title_terms if term in text]
            score += 0.01 * min(len(overlap), 5)
            candidates.append(
                MechanismMatch(
                    mechanism=mechanism,
                    score=round(min(score, 1.0), 4),
                    matched_keywords=matched_conditions,
                    conditions_met=True,
                )
            )

        # Actor-specific mechanisms dominate generic mechanisms for the same
        # event type and direction (a BOJ hike is not a Fed hike).
        actor_specific = [m for m in candidates if m.mechanism.actors]
        if actor_specific:
            candidates = [
                m for m in candidates if m.mechanism.actors or m.mechanism.event_types != actor_specific[0].mechanism.event_types
            ]
        candidates.sort(key=lambda item: (-item.score, item.mechanism.id))
        return candidates

    def evaluate(self, event: MacroEvent) -> list[dict]:
        """Return an audit trail of why each mechanism was accepted or rejected."""
        rows = []
        text = f"{event.headline} {event.summary} {' '.join(event.keywords)}".lower()
        for mechanism in self.knowledge.mechanisms:
            reason = "accepted"
            if event.event_type not in mechanism.event_types:
                reason = "event_type_mismatch"
            elif mechanism.directions and event.direction not in mechanism.directions:
                reason = "direction_mismatch"
            elif mechanism.actors and (event.actor is None or event.actor not in mechanism.actors):
                reason = "actor_mismatch"
            elif mechanism.any_keywords and not any(_contains(text, kw) for kw in mechanism.any_keywords):
                reason = "condition_missing"
            elif any(_contains(text, kw) for kw in mechanism.none_keywords):
                reason = "exclusion_keyword"
            rows.append(
                {
                    "id": mechanism.id,
                    "event_type_match": event.event_type in mechanism.event_types,
                    "direction_match": not mechanism.directions or event.direction in mechanism.directions,
                    "actor_match": not mechanism.actors or event.actor in mechanism.actors,
                    "reason": reason,
                }
            )
        return rows
