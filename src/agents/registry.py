"""
Agent Prompt Registry

Loads all YAML prompt templates and provides lookup functions:
  - get_prompt(id)           -> single prompt dict or None
  - list_prompts(category, instrument) -> filtered list of prompts
  - get_prompts_for_instrument(key) -> all prompts for a given instrument
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# ── Internal cache ────────────────────────────────────────────────────
_all_prompts: List[Dict[str, Any]] = []
_by_id: Dict[str, Dict[str, Any]] = {}
_loaded = False


def _load_all() -> None:
    """Walk the prompts/ directory tree and load every YAML file."""
    global _all_prompts, _by_id, _loaded
    if _loaded:
        return

    _all_prompts = []
    _by_id = {}

    for root, _dirs, files in os.walk(_PROMPTS_DIR):
        for fname in sorted(files):
            if not fname.endswith((".yaml", ".yml")):
                continue
            fpath = Path(root) / fname
            with open(fpath, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if not data or "prompts" not in data:
                continue
            for entry in data["prompts"]:
                entry.setdefault("_source_file", str(fpath.relative_to(_PROMPTS_DIR)))
                _all_prompts.append(entry)
                pid = entry.get("id")
                if pid:
                    if pid in _by_id:
                        raise ValueError(
                            f"Duplicate prompt id '{pid}' found in "
                            f"{entry['_source_file']} and {_by_id[pid]['_source_file']}"
                        )
                    _by_id[pid] = entry

    _loaded = True


# ── Public API ────────────────────────────────────────────────────────

def get_prompt(prompt_id: str) -> Optional[Dict[str, Any]]:
    """Return a single prompt template by its unique id, or None."""
    _load_all()
    return _by_id.get(prompt_id)


def list_prompts(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    instrument: Optional[str] = None,
    model: Optional[str] = None,
    schedule: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return prompt templates matching ALL supplied filters.
    Omitted filters are not applied (returns broader results).
    """
    _load_all()
    results = _all_prompts
    if category is not None:
        results = [p for p in results if p.get("category") == category]
    if subcategory is not None:
        results = [p for p in results if p.get("subcategory") == subcategory]
    if instrument is not None:
        results = [p for p in results if p.get("instrument") == instrument]
    if model is not None:
        results = [p for p in results if p.get("model") == model]
    if schedule is not None:
        results = [p for p in results if p.get("schedule") == schedule]
    return results


def get_prompts_for_instrument(key: str) -> List[Dict[str, Any]]:
    """
    Return every prompt template that targets a specific instrument.
    Includes instrument-specific prompts AND cross-instrument prompts
    (instrument=null) that process all instruments.
    """
    _load_all()
    return [
        p for p in _all_prompts
        if p.get("instrument") == key or p.get("instrument") is None
    ]


def get_all_ids() -> List[str]:
    """Return a sorted list of every prompt id."""
    _load_all()
    return sorted(_by_id.keys())


def count_prompts() -> Dict[str, int]:
    """Return prompt counts by category."""
    _load_all()
    counts: Dict[str, int] = {}
    for p in _all_prompts:
        cat = p.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def summary() -> Dict[str, Any]:
    """Return a high-level summary of the prompt registry."""
    _load_all()
    categories = count_prompts()
    models = {}
    schedules = {}
    for p in _all_prompts:
        m = p.get("model", "unknown")
        models[m] = models.get(m, 0) + 1
        s = p.get("schedule", "unknown")
        schedules[s] = schedules.get(s, 0) + 1
    return {
        "total_prompts": len(_all_prompts),
        "by_category": categories,
        "by_model": models,
        "by_schedule": schedules,
    }


def reload() -> None:
    """Force reload all prompt files (useful after edits)."""
    global _loaded
    _loaded = False
    _load_all()
