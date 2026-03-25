# Cot-ExplorerV2

## Overview
CFTC COT analysis + SMC trading engine + 310+ agent prompts + security framework

## Structure
- `src/trading/` -- Trading engine (COT, SMC, backtesting, Pine Scripts)
- `src/security/` -- Promptfoo + OpenViking security framework
- `agents/` -- 310+ agent prompt library (12 categories)
- `frontend/` -- Dashboard

## Commands
- `python src/trading/core/fetch_cot.py` -- Fetch CFTC COT data
- `python src/trading/core/fetch_all.py` -- Run full analysis pipeline
- `python scripts/validate-agents.py` -- Validate agent prompt schema
- `python scripts/build-agent-index.py` -- Build agent catalog
- `npx promptfoo eval -c src/security/promptfoo/configs/red-team.yaml` -- Run security tests

## Data Sources (all legal, free tier)
- CFTC.gov (public domain)
- FRED (public domain)
- Yahoo Finance (personal use)
- Stooq (free, no key)
- Twelvedata (800/day free)
- Finnhub (60/min free)

## Rules
- Real data only -- no synthetic/placeholder data
- stdlib Python for core scrapers (zero dependencies)
- All agents must validate against agents/_schema.json
