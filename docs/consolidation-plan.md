# Root -> src/ Consolidation Plan

## Summary

The project has 10 root-level Python scripts and 7 corresponding files in `src/trading/core/`. The src/ versions are consistently cleaner rewrites: they wrap logic in `main()` functions with `if __name__ == "__main__"` guards, use proper logging instead of bare `print()`, have English docstrings, and resolve paths relative to PROJECT_ROOT via `os.path.join(_DIR, "..", "..", "..")`. However, neither set delegates to the extracted `src/analysis/` modules (scoring.py, levels.py, setup_builder.py, technical.py, cot_analyzer.py, sentiment.py, smc.py) -- both root and src/trading/core versions contain their own inline implementations of the same logic. The pipeline runner (`src/pipeline/runner.py`) calls **root scripts via subprocess**, making the root scripts the actual production entry points while the src/ copies are effectively unused. Three `build_*` scripts have no src/ counterpart at all.

---

## File-by-File Analysis

### fetch_all.py
- **Root version**: 1244 lines, 21 functions. Top-level execution (no `main()` guard for the pipeline loop). Writes to `data/macro/latest.json`. Norwegian comments/print statements. Uses `from pathlib import Path` for BASE. Contains richer output JSON: includes `dxy_conf`, `vix_spread_factor`, `cot.date`, `cot.report`, full fundamentals breakdown with categories/indicators/usd_bias, copper_5d, em_5d in dollar_smile inputs.
- **src/ version**: 1041 lines, 22 functions (adds `main()`). Writes to `data/prices/macro_latest.json`. English docstrings/log messages. Uses `os.path` for all paths. Cleaner structure but slightly leaner output: omits `dxy_conf`, `vix_spread_factor`, `cot.date`, `cot.report`, and the full fundamentals categories/indicators breakdown.
- **Functions only in root**: none unique (all 21 root functions exist in src/ with identical signatures)
- **Functions only in src/**: `main()` (wraps the pipeline loop)
- **Neither delegates to src/analysis/**: Both contain inline `calc_atr`, `calc_ema`, `to_4h`, `get_pdh_pdl_pdc`, `get_pwh_pwl`, `get_session_status`, `find_intraday_levels`, `find_swing_levels`, `is_at_level`, `merge_tagged_levels`, `make_setup_l2l`, `fetch_fear_greed`, `fetch_news_sentiment`, `fetch_macro_indicators`, `detect_conflict` -- all duplicated from `src/analysis/`.
- **Output path difference**: Root writes `data/macro/latest.json`, src/ writes `data/prices/macro_latest.json`.
- **Recommendation**: Root is the richer version (more data in output JSON) and is what `update.sh` and `runner.py` actually call. **Keep root as canonical until refactored to import from src/analysis/**, then convert root to a thin wrapper calling `main()` from src/. The src/trading/core version can be deleted once the root imports from src/analysis/ modules. Priority: HIGH (1244 lines of duplicated logic).

### fetch_fundamentals.py
- **Root version**: 524 lines, 6 functions. Top-level execution. Writes to `data/fundamentals/latest.json`. Norwegian comments. Uses `pathlib.Path` for BASE.
- **src/ version**: 456 lines, 7 functions (adds `main()`). Writes to `data/prices/fundamentals_latest.json`. English docstrings. Uses `os.path`.
- **Functions only in root**: none unique
- **Functions only in src/**: `main()` (wraps execution)
- **Key difference**: Root `try_calendar_pmi()` reads from `data/calendar/latest.json` (hardcoded path). src/ version takes `data_dir` parameter, reads from `data_dir/prices/calendar_latest.json`. Root output path differs.
- **Recommendation**: **Merge into src/, delete root copy, add thin wrapper.** The logic is identical; src/ version is cleaner with parameterized paths. Priority: MEDIUM.

### fetch_cot.py
- **Root version**: 251 lines, 6 functions. Top-level execution. Writes to `data/{report_id}/`. Rich `MARKET_NO` dict (78 entries) for Norwegian market name translations. Uses `pathlib.Path` for data dirs.
- **src/ version**: 361 lines, 7 functions (adds `main()`). Writes to `data/cot/`. Same `MARKET_NO` dict. English docstrings. Uses `os.path`. Longer because of more detailed inline comments and docstrings.
- **Functions only in root**: none unique
- **Functions only in src/**: `main()` (wraps execution)
- **Key difference**: Output directories differ (`data/tff/` vs `data/cot/tff/`). src/ version nests all COT data under `data/cot/`. Root has `--history` flag support via `sys.argv`; src/ has same.
- **Recommendation**: **Keep src/ version as canonical.** It has cleaner path organization under `data/cot/`. Delete root copy, add thin wrapper. Priority: LOW (well-contained, rarely changed).

### fetch_prices.py
- **Root version**: 113 lines, 1 function (`fetch_yahoo`). Top-level execution (no main guard). Writes to `data/macro/latest.json`. Inline dollar smile / VIX regime logic. Norwegian print/comments. Missing `import urllib.parse` at top (imported late at line 56).
- **src/ version**: 157 lines, 3 functions (`fetch_yahoo`, `build_macro`, `main`). Writes to `data/prices/macro_latest.json`. Properly structured with extracted `build_macro()`. English comments.
- **Functions only in root**: none (just unstructured code)
- **Functions only in src/**: `build_macro()`, `main()`
- **Recommendation**: **Delete root, keep src/ version.** The root version is a quick-and-dirty script; src/ is properly structured. However, note that `fetch_all.py` already subsumes all of this functionality. This script may be redundant once fetch_all.py is consolidated. Priority: LOW (redundant with fetch_all.py).

### fetch_calendar.py
- **Root version**: 69 lines, 0 named functions. All top-level execution. Writes to `data/calendar/latest.json`. Calls `exit(1)` on error. Norwegian print. Field name `berorte` (Norwegian for "affected").
- **src/ version**: 108 lines, 2 functions (`fetch_calendar`, `main`). Writes to `data/prices/calendar_latest.json`. Returns `None` on error (no hard exit). Adds `"actual"` field to events. English comments.
- **Functions only in root**: none (no functions)
- **Functions only in src/**: `fetch_calendar()`, `main()`
- **Recommendation**: **Delete root, keep src/ version.** Root is unstructured inline code. src/ has proper function extraction and is more robust (no `exit(1)`). Priority: LOW.

### push_signals.py
- **Root version**: 191 lines. Mix of functions and top-level execution. Reads `data/macro.json`. Uses emojis in output. Norwegian comments.
- **src/ version**: 218 lines, 7 functions + `main()`. Reads `data/prices/macro_latest.json`. No emojis. English comments. Fully wrapped in functions.
- **Functions only in root**: none unique
- **Functions only in src/**: `load_data()`, `get_top_signals()`, `main()`
- **Key difference**: Root reads `data/macro.json`, src/ reads `data/prices/macro_latest.json`. This path difference means they read from different data files. Root has top-level side effects (loads data, builds message, pushes -- all at import time).
- **Recommendation**: **Delete root, keep src/ version.** The src/ version has proper function extraction and no import-time side effects. Priority: MEDIUM (push_signals must match the output path of whatever fetch_all.py produces).

### smc.py
- **Root version**: 288 lines, 9 functions + `__main__` test block. Norwegian comments. Returns dict with plain keys.
- **src/trading/core/ version**: 299 lines, 9 functions + `__main__` test block. English comments/docstrings. Identical logic. Returns same dict structure.
- **src/analysis/smc.py**: 249 lines (without test block). Has type hints (`Row = tuple[float, float, float]`). Same 9 functions. Norwegian/mixed comments. Imported by nothing currently.
- **Three copies exist**: root `smc.py`, `src/trading/core/smc.py`, `src/analysis/smc.py`
- **Functions**: All three have identical function sets: `calc_atr`, `find_pivot_highs`, `find_pivot_lows`, `classify_swings`, `build_supply_demand_zones`, `detect_bos`, `determine_structure`, `filter_relevant_zones`, `run_smc`
- **Recommendation**: **Consolidate to src/analysis/smc.py** (the only one with type hints). Root `smc.py` should become `from src.analysis.smc import run_smc` (1-line wrapper). Delete `src/trading/core/smc.py`. Priority: HIGH (3 copies of identical code).

---

## Build Scripts (no src/ counterpart)

### build_timeseries.py (162 lines)
- **Purpose**: Reads `data/history/{report}/*.json` + `data/{report}/latest.json`, deduplicates by date, outputs per-market time series to `data/timeseries/{symbol}_{report}.json` + `index.json`. Used for the COT historical chart feature.
- **Where logic should live**: `src/trading/core/build_timeseries.py` or `src/pipeline/stages/combine_timeseries.py`. Pure data transformation, no external fetching.
- **Dependencies**: Only reads local JSON files (no HTTP calls). Uses pathlib + json + os.
- **Recommendation**: Move to `src/pipeline/` and wrap in a `main()` function. Not called by update.sh, so lower priority.

### build_price_history.py (94 lines)
- **Purpose**: Fetches 15-year weekly price history from Yahoo Finance for 17 instruments. Saves per-instrument JSON to `data/prices/{key}.json` plus a `cot_map.json` mapping COT symbols to price keys.
- **Where logic should live**: `src/trading/core/fetch_price_history.py`. It's a data fetcher (HTTP calls to Yahoo), distinct from `fetch_prices.py` which gets current data.
- **Dependencies**: Yahoo Finance HTTP calls. Standalone, not called by update.sh or runner.py.
- **Recommendation**: Move to `src/trading/core/` with `main()` wrapper. Rename to `fetch_price_history.py` for naming consistency. Low priority since it's a one-time/manual script.

### build_combined.py (67 lines)
- **Purpose**: Merges latest COT data from multiple report types (tff, legacy, disaggregated, supplemental) into `data/combined/latest.json`, deduplicating by market name with priority ordering.
- **Where logic should live**: `src/pipeline/stages/combine_cot.py` or `src/trading/core/build_combined.py`.
- **Dependencies**: Only reads local JSON files. Called by `update.sh`.
- **Recommendation**: Move to `src/trading/core/` with `main()` wrapper. MEDIUM priority since update.sh calls it directly.

---

## Pipeline Integration

### How runner.py calls scripts: **SUBPROCESS to root scripts**
`src/pipeline/runner.py` uses `subprocess.run([sys.executable, "fetch_calendar.py"], check=False)` for all stages. It calls:
- `fetch_calendar.py` (root)
- `fetch_cot.py` (root)
- `fetch_fundamentals.py` (root)
- `fetch_prices.py` (root)
- `fetch_all.py` (root)
- `push_signals.py` (root)

It does NOT import from `src/trading/core/` at all. The only src/ import is `src/publishers.json_file.publish_static_json` in the output stage and `src.security.audit_log.log_event` for audit logging.

**Implication**: The src/trading/core/ copies of these scripts are currently dead code -- nothing imports or invokes them.

### How update.sh calls scripts: **Root scripts directly**
`update.sh` runs:
1. `python3 fetch_calendar.py`
2. `python3 fetch_cot.py`
3. `python3 build_combined.py`
4. `python3 fetch_fundamentals.py` (conditional, every 12h)
5. `python3 fetch_all.py`
6. `python3 push_signals.py` (conditional, if bot configured)

All root paths. Does NOT reference anything in `src/`.

---

## Data Path Inconsistency

Root and src/ scripts write to different output directories:

| Script | Root output | src/ output |
|--------|------------|-------------|
| fetch_all.py | `data/macro/latest.json` | `data/prices/macro_latest.json` |
| fetch_fundamentals.py | `data/fundamentals/latest.json` | `data/prices/fundamentals_latest.json` |
| fetch_cot.py | `data/{report}/latest.json` | `data/cot/{report}/latest.json` |
| fetch_prices.py | `data/macro/latest.json` | `data/prices/macro_latest.json` |
| fetch_calendar.py | `data/calendar/latest.json` | `data/prices/calendar_latest.json` |
| push_signals.py | reads `data/macro.json` | reads `data/prices/macro_latest.json` |

**Recommendation**: Standardize on the src/ convention (`data/prices/` for derived data, `data/cot/` for COT data) when consolidating.

---

## src/analysis/ Module Status

These modules were extracted from v1 fetch_all.py but are **not imported by anything in production**:

| Module | Lines | Extracted from | Status |
|--------|-------|---------------|--------|
| `scoring.py` | 75 | fetch_all.py L987-1014 | Uses Pydantic models. Dead code. |
| `levels.py` | 171 | fetch_all.py L267-368 | Uses Pydantic models. Dead code. |
| `setup_builder.py` | 200 | fetch_all.py L371-527 | Imports from `levels.py`. Dead code. |
| `technical.py` | 75 | fetch_all.py L243-265 | Uses Pydantic models. Dead code. |
| `cot_analyzer.py` | 69 | fetch_all.py L898-908 | Pure functions. Dead code. |
| `sentiment.py` | 249 | fetch_all.py L529-682 | HTTP fetchers. Dead code. |
| `smc.py` | 249 | smc.py | Type-hinted copy. Dead code. |

These are well-extracted, properly typed, and have good docstrings -- they should become the canonical implementations.

---

## Recommended Consolidation Order

1. **smc.py** (HIGH, low risk) -- 3 identical copies. Make `src/analysis/smc.py` canonical. Root `smc.py` becomes `from src.analysis.smc import run_smc; __all__ = ["run_smc"]`. Delete `src/trading/core/smc.py`. Verify `fetch_all.py`'s `from smc import run_smc` still works.

2. **fetch_calendar.py** (LOW risk, quick win) -- Root is 69 lines of inline code. Replace with thin wrapper calling `src/trading/core/fetch_calendar.main()`. Update output path to match.

3. **fetch_prices.py** (LOW risk) -- Root is 113 lines, redundant with fetch_all.py. Replace with thin wrapper. Consider deprecating entirely since fetch_all.py does the same work.

4. **fetch_fundamentals.py** (MEDIUM risk) -- Replace root with wrapper around src/ version. Unify output path.

5. **fetch_cot.py** (LOW risk) -- Replace root with wrapper. Unify output path under `data/cot/`.

6. **push_signals.py** (MEDIUM risk, path-dependent) -- Must be done AFTER fetch_all.py output path is decided. Replace root with wrapper.

7. **build_combined.py** (LOW) -- Move to `src/trading/core/` or `src/pipeline/`. Update `update.sh`.

8. **build_timeseries.py** (LOW) -- Move to `src/pipeline/`. Not in critical path.

9. **build_price_history.py** (LOW) -- Move to `src/trading/core/`. Manual-run script.

10. **fetch_all.py** (HIGH risk, highest impact) -- The big one. Refactor to import from `src/analysis/` modules instead of inlining 21 functions. This eliminates ~800 lines of duplication. Must be done carefully since it's the central pipeline script. Steps:
    - Replace inline `calc_atr`, `calc_ema`, `to_4h` with imports from `src/analysis/technical`
    - Replace inline level functions with imports from `src/analysis/levels`
    - Replace inline `make_setup_l2l` with import from `src/analysis/setup_builder`
    - Replace inline sentiment/macro functions with imports from `src/analysis/sentiment`
    - Replace inline COT classification with imports from `src/analysis/cot_analyzer`
    - Replace inline scoring with import from `src/analysis/scoring`
    - Update `runner.py` to call `from src.trading.core.fetch_all import main` instead of subprocess

11. **runner.py** (LAST) -- After all scripts are consolidated, replace subprocess calls with direct imports. This eliminates process overhead and enables proper error propagation.
