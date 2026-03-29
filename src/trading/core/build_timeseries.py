#!/usr/bin/env python3
"""Build data/timeseries/{symbol}_{report}.json from data/history/.

One file per market with all weekly data points sorted chronologically.
Prioritises disaggregated > tff > legacy > supplemental for spec_net.
"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

REPORTS = ["disaggregated", "tff", "legacy", "supplemental"]
MIN_WEEKS = 10


def _ingest_rows(rows: list[dict], report: str, markets: dict) -> None:
    """Ingest a list of COT rows into *markets* accumulator."""
    for row in rows:
        sym = row.get("symbol", "").strip()
        mkt = row.get("market", "").strip()
        date = row.get("date", "").strip()
        spec = row.get("spekulanter", {}) or {}
        net = spec.get("net")
        if not sym or not mkt or not date or net is None:
            continue

        key = (sym, report)
        if key not in markets:
            markets[key] = {
                "symbol": sym,
                "market": mkt,
                "navn_no": row.get("navn_no", mkt),
                "kategori": row.get("kategori", "annet"),
                "report": report,
                "data": {},
            }

        markets[key]["data"][date] = {
            "date": date,
            "spec_net": net,
            "spec_long": spec.get("long", 0) or 0,
            "spec_short": spec.get("short", 0) or 0,
            "oi": row.get("open_interest", 0) or 0,
        }


def build_timeseries(base_dir: str | Path | None = None) -> dict:
    """Build timeseries JSON files.

    Parameters
    ----------
    base_dir : path, optional
        Root ``data/`` directory.  Defaults to ``<project>/data``.

    Returns
    -------
    dict with keys ``written``, ``skipped``, ``index_count``.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[3] / "data"
    base_dir = Path(base_dir)

    hist_dir = base_dir / "cot" / "history"
    ts_dir = base_dir / "timeseries"
    ts_dir.mkdir(parents=True, exist_ok=True)

    markets: dict = {}

    # -- ingest history files --
    for report in REPORTS:
        rdir = hist_dir / report
        if not rdir.exists():
            log.warning("Missing: %s", rdir)
            continue

        files = sorted(os.listdir(rdir))
        log.info("%s: %d year-files", report, len(files))

        for fname in files:
            if not fname.endswith(".json"):
                continue
            try:
                with open(rdir / fname, encoding="utf-8") as f:
                    rows = json.load(f)
            except (ValueError, KeyError):
                continue
            _ingest_rows(rows, report, markets)

    # -- ingest latest.json for each report --
    for report in REPORTS:
        latest = base_dir / "cot" / report / "latest.json"
        if not latest.exists():
            continue
        try:
            with open(latest, encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:
            continue
        _ingest_rows(rows, report, markets)

    # -- write timeseries files --
    written = 0
    skipped = 0
    for (sym, report), meta in markets.items():
        data_sorted = sorted(meta["data"].values(), key=lambda x: x["date"])
        if len(data_sorted) < MIN_WEEKS:
            skipped += 1
            continue

        out = {
            "symbol": meta["symbol"],
            "market": meta["market"],
            "navn_no": meta["navn_no"],
            "kategori": meta["kategori"],
            "report": report,
            "weeks": len(data_sorted),
            "data": data_sorted,
        }
        fpath = ts_dir / f"{sym.lower()}_{report}.json"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        written += 1

    # -- build index.json --
    index = []
    for (sym, report), meta in markets.items():
        n = len(meta["data"])
        if n < MIN_WEEKS:
            continue
        index.append(
            {
                "key": f"{sym}_{report}",
                "symbol": sym,
                "navn_no": meta["navn_no"],
                "market": meta["market"],
                "kategori": meta["kategori"],
                "report": report,
                "weeks": n,
            }
        )

    index.sort(key=lambda x: (-x["weeks"], x["navn_no"]))
    with open(ts_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    log.info("Done! %d files written, %d skipped (<%d weeks)", written, skipped, MIN_WEEKS)
    log.info("Index: %d markets", len(index))

    for entry in index[:10]:
        log.info("  %4d weeks  %-30s  %s", entry["weeks"], entry["navn_no"], entry["report"])

    return {"written": written, "skipped": skipped, "index_count": len(index)}


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    build_timeseries()


if __name__ == "__main__":
    main()
