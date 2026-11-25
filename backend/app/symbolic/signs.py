"""Qualitative sign algebra.

A sign is one of +, -, 0, ?. Parallel influences combine by qualitative
addition (agreement -> definite, conflict -> ?), and serial influences combine
by multiplication. This is the classic qualitative-reasoning algebra, applied
to macro transmission channels and asset loadings.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class Sign(str, Enum):
    POS = "+"
    NEG = "-"
    ZERO = "0"
    AMBIGUOUS = "?"

    @property
    def is_definite(self) -> bool:
        return self in (Sign.POS, Sign.NEG)


def from_number(value: float, tolerance: float = 1e-9) -> Sign:
    if abs(value) <= tolerance:
        return Sign.ZERO
    return Sign.POS if value > 0 else Sign.NEG


def mul(left: Sign, right: Sign) -> Sign:
    if left is Sign.ZERO or right is Sign.ZERO:
        return Sign.ZERO
    if left is Sign.AMBIGUOUS or right is Sign.AMBIGUOUS:
        return Sign.AMBIGUOUS
    return Sign.POS if left is right else Sign.NEG


def combine(signs: Iterable[Sign]) -> Sign:
    """Qualitative addition of parallel influences."""
    nonzero = [sign for sign in signs if sign is not Sign.ZERO]
    if not nonzero:
        return Sign.ZERO
    if any(sign is Sign.AMBIGUOUS for sign in nonzero):
        return Sign.AMBIGUOUS
    if all(sign is Sign.POS for sign in nonzero):
        return Sign.POS
    if all(sign is Sign.NEG for sign in nonzero):
        return Sign.NEG
    return Sign.AMBIGUOUS


def to_int(sign: Sign) -> int | None:
    return {"+": 1, "-": -1, "0": 0}.get(sign.value)


def direction_word(sign: Sign) -> str:
    return {
        Sign.POS: "increases",
        Sign.NEG: "decreases",
        Sign.ZERO: "unchanged",
        Sign.AMBIGUOUS: "ambiguous",
    }[sign]
