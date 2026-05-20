"""Google-dorking sub-investigation.

Compiles a target-specific set of search queries from `catalog.py`, runs
them against a primary backend (Google CSE) and falls back to DuckDuckGo
when Google rate-limits / returns 0 results. Persists runs + findings
into the indicator schema so they show up in the investigation history.
"""
from app.dorking.catalog import CATEGORIES, build_dorks
from app.dorking.runner import run_dorks

__all__ = ["CATEGORIES", "build_dorks", "run_dorks"]
