"""Uvicorn entry point.

From the repository root:
    uvicorn backend.main:app --reload

From the backend directory:
    uvicorn main:app --reload
"""

try:  # package import (repository root)
    from backend.app.api import app
except ModuleNotFoundError:  # direct import (backend directory)
    from app.api import app

__all__ = ["app"]
