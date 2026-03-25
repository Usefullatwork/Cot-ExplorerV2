# Cot-ExplorerV2

**CFTC COT analysis + Smart Money Concepts trading engine + 310+ agent prompts + security framework**

A comprehensive trading intelligence platform that combines institutional positioning data (CFTC Commitments of Traders), Smart Money Concepts (SMC) technical analysis, fundamental macro scoring, and a library of 310+ AI agent prompts -- all built with zero external Python dependencies.

## Features

- **COT Analysis** -- Downloads and parses all 4 CFTC report types (TFF, Legacy, Disaggregated, Supplemental) with Norwegian market name mapping and category classification
- **SMC Engine** -- Full Smart Money Concepts implementation: swing structure (HH/LH/HL/LL), supply/demand zones, break of structure (BOS), multi-timeframe analysis (15m/1H/4H)
- **Fundamental Scoring** -- EdgeFinder-style macro scoring with FRED data: GDP, CPI, NFP, Claims, JOLTS + weighted category consensus
- **Multi-Source Pricing** -- Priority waterfall: Twelvedata -> Stooq -> Yahoo Finance, with Finnhub realtime overlay
- **12-Point Scoring** -- Each instrument scored on SMA200, momentum, COT, fundamentals, SMC structure, news sentiment, event risk
- **Dollar Smile Model** -- Dynamic USD regime classification with VIX, HY spreads, yield curve
- **Signal Dispatch** -- Push top setups to Telegram, Discord, and Flask endpoints
- **310+ Agent Prompts** -- Curated library across 12 domains with validated schema
- **Security Framework** -- Promptfoo red-team testing + OpenViking integration

## Architecture

```
Cot-ExplorerV2/
|
|-- src/trading/
|   |-- core/              # Main pipeline scripts
|   |   |-- fetch_cot.py       # CFTC COT data downloader
|   |   |-- fetch_all.py       # Full analysis orchestrator
|   |   |-- fetch_prices.py    # Live price fetcher
|   |   |-- fetch_fundamentals.py  # FRED macro scorer
|   |   |-- fetch_calendar.py  # Economic calendar
|   |   |-- smc.py             # SMC engine (Pine Script port)
|   |   |-- push_signals.py    # Telegram/Discord dispatch
|   |
|   |-- scrapers/          # Data source modules
|   |   |-- yahoo_finance.py   # Yahoo Finance v8 API
|   |   |-- stooq.py           # Stooq daily CSV
|   |   |-- twelvedata.py      # Twelvedata REST API
|   |   |-- finnhub.py         # Finnhub realtime quotes
|   |   |-- fred.py            # FRED economic data
|   |   |-- alpha_vantage.py   # Alpha Vantage (new)
|   |   |-- cnn_fear_greed.py  # CNN Fear & Greed Index
|   |
|   |-- backtesting/       # Strategy backtesting framework
|   |-- pine_scripts/      # TradingView Pine Script library
|   |-- signals/           # Signal generation and filtering
|
|-- src/security/
|   |-- promptfoo/         # LLM red-team testing
|   |-- openviking/        # OpenViking security adapters
|
|-- agents/                # 310+ agent prompt library
|   |-- _schema.json           # Agent validation schema
|   |-- _template.md           # Agent authoring template
|   |-- 01-development/        # Dev agents (coder, reviewer, etc.)
|   |-- 02-security/           # Security agents
|   |-- ...
|   |-- 12-meta-agents/        # Meta/orchestration agents
|
|-- data/                  # Runtime data (gitignored)
|-- frontend/              # Dashboard UI
|-- scripts/               # Utility scripts
|-- tests/                 # Test suite
```

## Quick Start

```bash
# Clone
git clone https://github.com/Usefullatwork/Cot-ExplorerV2.git
cd Cot-ExplorerV2

# Fetch COT data (no dependencies needed)
python src/trading/core/fetch_cot.py

# Fetch economic calendar
python src/trading/core/fetch_calendar.py

# Set optional API keys for enhanced data
export FRED_API_KEY="your-key"
export TWELVEDATA_API_KEY="your-key"
export FINNHUB_API_KEY="your-key"

# Fetch fundamentals
python src/trading/core/fetch_fundamentals.py

# Run full analysis pipeline
python src/trading/core/fetch_all.py

# Push signals (configure tokens first)
export TELEGRAM_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python src/trading/core/push_signals.py
```

## Data Sources

| Source | Data | Rate Limit | Key Required |
|--------|------|------------|--------------|
| CFTC.gov | COT reports (4 types) | Unlimited | No |
| FRED | GDP, CPI, NFP, rates | 120/min | Yes (free) |
| Yahoo Finance | OHLC, quotes | Unofficial | No |
| Stooq | Daily OHLC | Unlimited | No |
| Twelvedata | OHLC, forex | 800/day | Yes (free) |
| Finnhub | Realtime quotes | 60/min | Yes (free) |
| Alpha Vantage | OHLC, forex | 25/day | Yes (free) |
| CNN | Fear & Greed Index | Unofficial | No |
| ForexFactory | Economic calendar | Unofficial | No |

## Agent Library (310+ prompts)

| Category | Directory | Count | Examples |
|----------|-----------|-------|----------|
| Development | `01-development/` | 30+ | Coder, Reviewer, Tester, Refactorer |
| Security | `02-security/` | 25+ | Auditor, Pen Tester, Threat Modeler |
| Trading | `03-trading/` | 35+ | COT Analyst, SMC Trader, Risk Manager |
| Data & ML | `04-data-ml/` | 30+ | Data Scientist, ML Engineer, NLP |
| DevOps | `05-devops-infra/` | 25+ | CI/CD, Docker, Kubernetes, Terraform |
| SEO & Marketing | `06-seo-marketing/` | 20+ | SEO Auditor, Content Writer |
| Product & Design | `07-product-design/` | 20+ | UX Researcher, PM, A/B Tester |
| Project Management | `08-project-management/` | 15+ | Sprint Planner, Agile Coach |
| Writing & Docs | `09-writing-docs/` | 20+ | Technical Writer, API Docs |
| Orchestration | `10-orchestration/` | 25+ | Swarm Coordinator, Router |
| Domain-Specific | `11-domain-specific/` | 35+ | Healthcare, Legal, Finance |
| Meta-Agents | `12-meta-agents/` | 30+ | Self-Improver, Evaluator |

## Scoring System

Each instrument is scored on 12 criteria (0-12 points):

1. Above SMA200 (daily trend)
2. 20-day momentum confirms direction
3. COT confirms direction
4. COT strong positioning (>10% of OI)
5. Price AT HTF level now
6. HTF level nearby (D1/Weekly)
7. D1 + 4H trend aligned
8. No high-impact events within 4 hours
9. News sentiment confirms
10. Fundamentals confirm
11. BOS 1H/4H confirms direction
12. SMC 1H structure confirms

**Grades:** A+ (11+) | A (9+) | B (6+) | C (<6)

**Timeframe classification:**
- MAKRO: Score >= 6 + COT confirms + HTF level (hold days/weeks)
- SWING: Score >= 4 + HTF level (hold hours/days)
- SCALP: Score >= 2 + at level + active session (minutes)
- WATCHLIST: Not ready

## License

MIT
