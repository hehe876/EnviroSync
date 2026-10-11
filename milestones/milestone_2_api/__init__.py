"""Milestone 2: read-only FastAPI application, depends on Milestone 1B.

Run: python -m uvicorn milestones.milestone_2_api:app --host 127.0.0.1
"""
from .app import app
from .dependencies import get_federation
__all__ = ["app", "get_federation"]
