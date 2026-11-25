"""Test fixtures and path setup."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def engine():
    from backend.app.reasoning.engine import AnalysisEngine

    return AnalysisEngine()


@pytest.fixture(scope="session")
def knowledge():
    from backend.app.knowledge.loader import load_knowledge

    return load_knowledge()
