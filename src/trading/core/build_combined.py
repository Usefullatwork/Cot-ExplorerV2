#!/usr/bin/env python3
"""Build data/combined/latest.json from the latest COT reports.

Reads from ``data/{report}/latest.json`` and merges them with priority:
tff > disaggregated > legacy > supplemental.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

REPORTS = ["tff", "legacy", "disaggregated", "supplemental"]
RAPPORT_PRIORITET = {"tff": 0, "disaggregated": 1, "legacy": 2, "supplemental": 3}


def build_combined(base_dir: str | Path | None = None) -> list[dict]:
    """Merge COT reports into a single combined file.

    Parameters
    ----------
    base_dir : path, optional
        Root ``data/`` directory.  Defaults to ``<project>/data``.

    Returns
    -------
    list[dict]  The combined market entries, sorted by abs(spec_net) descending.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[3] / "data"
    base_dir = Path(base_dir)

    out_dir = base_dir / "combined"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "latest.json"

    seen: dict[str, dict] = {}  # market.lower() -> entry

    for rep in REPORTS:
        fpath = base_dir / "cot" / rep / "latest.json"
        if not fpath.exists():
            log.warning("  Missing: %s", fpath)
            continue

        with open(fpath, encoding="utf-8") as f:
            rows = json.load(f)

        log.info("  %s: %d markets, date=%s", rep, len(rows), rows[0].get("date", "?") if rows else "?")

        for row in rows:
            market = row.get("market", "").strip()
            if not market:
                continue

            mk = market.lower()
            pri = RAPPORT_PRIORITET.get(rep, 9)

            if mk in seen and RAPPORT_PRIORITET.get(seen[mk]["report"], 9) <= pri:
                continue

            seen[mk] = {
                "symbol": row.get("symbol", ""),
                "market": market,
                "navn_no": row.get("navn_no") or market,
                "kategori": row.get("kategori", "annet"),
                "report": rep,
                "forklaring": row.get("forklaring", ""),
                "date": row.get("date", ""),
                "spekulanter": row.get("spekulanter", {}),
                "open_interest": row.get("open_interest", 0),
                "change_spec_net": row.get("change_spec_net", 0),
            }

    result = sorted(
        seen.values(),
        key=lambda x: abs((x.get("spekulanter") or {}).get("net", 0)),
        reverse=True,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    dato = result[0]["date"] if result else "?"
    log.info("OK: %d markets -> %s", len(result), out_path)
    log.info("COT date: %s", dato)

    return result


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    build_combined()


if __name__ == "__main__":
    main()
