"""Publish macro data as static JSON files in the exact v1 format."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path("data/macro")


def publish_static_json(
    macro_data: dict[str, Any],
    output_dir: str | Path | None = None,
) -> Path:
    """Write ``latest.json`` in the exact v1 format used by the frontend.

    Parameters
    ----------
    macro_data : dict
        Complete macro panel dict as produced by the pipeline.  Expected keys:
        ``date``, ``cot_date``, ``prices``, ``vix_regime``, ``dollar_smile``,
        ``trading_levels``, ``calendar``.
    output_dir : str or Path, optional
        Directory to write into.  Defaults to ``data/macro``.

    Returns
    -------
    Path
        Full path to the written file.
    """
    out = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    target = out / "latest.json"

    with open(target, "w", encoding="utf-8") as f:
        json.dump(macro_data, f, ensure_ascii=False, indent=2)

    logger.info("Published static JSON: %s (%d bytes)", target, target.stat().st_size)
    return target


if __name__ == "__main__":
    # CLI entry-point: read from DB or fallback and write latest.json
    from src.db import repository as repo

    snap = repo.get_latest_macro()
    if snap and snap.full_json:
        data = json.loads(snap.full_json)
    else:
        # Fallback: try to read existing file
        fallback = _DEFAULT_OUTPUT_DIR / "latest.json"
        if fallback.exists():
            with open(fallback, encoding="utf-8") as f:
                data = json.load(f)
        else:
            logger.error("No macro data available in DB or on disk.")
            raise SystemExit(1)

    publish_static_json(data)
    logger.info(f"OK: {_DEFAULT_OUTPUT_DIR / 'latest.json'}")
