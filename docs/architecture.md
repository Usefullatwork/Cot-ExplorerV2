# Architecture Document -- Cot-ExplorerV2

Last updated: 2026-03-25

---

## System Overview

```
+------------------------------------------------------------------+
|                        Cot-ExplorerV2                             |
+------------------------------------------------------------------+
|                                                                    |
|  +-------------------+    +-------------------+    +-----------+  |
|  |   DATA LAYER      |    |  ANALYSIS LAYER   |    | API LAYER |  |
|  |                   |    |                   |    |           |  |
|  | fetch_cot.py      |--->| scoring.py        |--->| FastAPI   |  |
|  | fetch_prices.py   |    | smc.py            |    | /signals  |  |
|  | fetch_fundamentals|    | levels.py         |    | /cot      |  |
|  | fetch_calendar.py |    | technical.py      |    | /macro    |  |
|  | fetch_all.py      |    | sentiment.py      |    | /instru.  |  |
|  |                   |    | cot_analyzer.py   |    | /webhook  |  |
|  |                   |    | setup_builder.py  |    | /health   |  |
|  +-------------------+    +-------------------+    +-----------+  |
|          |                        |                      |        |
|          v                        v                      v        |
|  +-------------------+    +-------------------+    +-----------+  |
|  |   DATABASE        |    |  SIGNAL DISPATCH  |    | FRONTEND  |  |
|  |                   |    |                   |    |           |  |
|  | SQLite via        |    | push_signals.py   |    | index.html|  |
|  | SQLAlchemy        |    | Telegram          |    | Dashboard |  |
|  | 10 tables         |    | Discord           |    | GH Pages  |  |
|  +-------------------+    +-------------------+    +-----------+  |
|                                                                    |
|  +-------------------+    +-------------------+    +-----------+  |
|  | SECURITY          |    |  AGENTS           |    | PINE      |  |
|  |                   |    |                   |    | SCRIPTS   |  |
|  | Promptfoo configs |    | 310+ prompts      |    | 6 indica- |  |
|  | Custom graders    |    | 12 categories     |    | tors +    |  |
|  | Input validator   |    | _schema.json      |    | 2 strat-  |  |
|  | Audit logging     |    | Validated schema  |    | egies     |  |
|  +-------------------+    +-------------------+    +-----------+  |
+------------------------------------------------------------------+
```

---

## Trading Engine Architecture

### Data Collection Pipeline

```
                     +------------------+
                     |   fetch_all.py   |
                     |  (Orchestrator)  |
                     +--------+---------+
                              |
         +--------------------+--------------------+
         |                    |                    |
         v                    v                    v
+----------------+  +------------------+  +------------------+
|  fetch_cot.py  |  | fetch_prices.py  |  |fetch_fundament.py|
|                |  |                  |  |                  |
| CFTC.gov       |  | Twelvedata (1st) |  | FRED API         |
| 4 report types |  | Stooq (2nd)      |  | GDP, CPI, NFP    |
| TFF, Legacy,   |  | Yahoo (3rd)      |  | Claims, JOLTS    |
| Disagg, Suppl. |  | Finnhub (overlay)|  | EdgeFinder-style |
+----------------+  +------------------+  +------------------+
         |                    |                    |
         v                    v                    v
+----------------------------------------------------------+
|                    SQLite Database                         |
|                                                           |
| instruments | prices_daily | prices_intraday | cot_pos.  |
| signals     | backtest_results | fundamentals            |
| macro_snapshots | calendar_events | audit_log            |
+----------------------------------------------------------+
```

### Analysis Pipeline

```
Raw Data (DB/JSON)
      |
      v
+--------------------+     +--------------------+
| technical.py       |     | cot_analyzer.py    |
| calc_atr()         |     | classify_cot_bias()|
| calc_ema()         |     | classify_momentum()|
| to_4h()            |     | get_cot_for_inst() |
+--------------------+     +--------------------+
      |                           |
      v                           v
+--------------------+     +--------------------+
| levels.py          |     | sentiment.py       |
| get_pdh_pdl_pdc()  |     | fetch_fear_greed() |
| get_pwh_pwl()      |     | fetch_news_sent()  |
| find_intraday_lvls |     | fetch_macro_ind()  |
| find_swing_levels()|     | detect_conflict()  |
| merge_tagged_lvls()|     +--------------------+
| is_at_level()      |           |
+--------------------+           |
      |                          |
      v                          v
+--------------------+     +--------------------+
| smc.py             |     | scoring.py         |
| run_smc()          |<--->| calculate_         |
| find_pivot_highs() |     |   confluence()     |
| find_pivot_lows()  |     | 12 boolean criteria|
| classify_swings()  |     | Grade: A+/A/B/C    |
| build_s/d_zones()  |     | Timeframe bias     |
| detect_bos()       |     +--------------------+
| determine_struct() |           |
+--------------------+           v
      |               +--------------------+
      +-------------->| setup_builder.py   |
                      | make_setup_l2l()   |
                      | Structural SL      |
                      | Level-to-level T1  |
                      | R:R calculation    |
                      +--------------------+
                              |
                              v
                      +--------------------+
                      | Signal Output      |
                      | - DB persistence   |
                      | - JSON export      |
                      | - Telegram/Discord |
                      | - API endpoint     |
                      +--------------------+
```

### Core Data Models

The Pydantic models in `src/core/models.py`:

| Model | Purpose |
|---|---|
| `Instrument` | Trading instrument definition (12 tracked) |
| `OhlcBar` | Single (high, low, close) price bar |
| `TaggedLevel` | Price level with source and weight |
| `ScoreDetail` | Single scoring criterion (label + bool) |
| `ScoringInput` | All 12 boolean inputs for scoring |
| `ScoringResult` | Score, grade, timeframe bias, details |
| `SetupL2L` | Level-to-level trade setup (entry, SL, T1, T2, R:R) |
| `SmcOutput` | SMC analysis output (structure, zones, BOS) |
| `MacroIndicator` | Single macro reading (price, chg1d, chg5d) |
| `FearGreed` | CNN Fear & Greed score and rating |
| `NewsSentiment` | Aggregated news sentiment (score, label, drivers) |

### Database Schema (10 Tables)

The SQLAlchemy ORM models in `src/db/models.py`:

| Table | Purpose | Key Indices |
|---|---|---|
| `instruments` | 12 tracked instruments | PK: key |
| `prices_daily` | Daily OHLC bars | instrument + date (unique) |
| `prices_intraday` | 15m/1H/4H bars | instrument + timestamp + timeframe (unique) |
| `cot_positions` | CFTC COT data | symbol + report_type + date (unique) |
| `signals` | Generated trade signals | instrument, generated_at, grade, score |
| `backtest_results` | Signal outcome tracking | signal_id (FK), instrument, entry_date |
| `fundamentals` | FRED macro indicators | indicator_key, updated_at |
| `macro_snapshots` | Full macro panel JSON | generated_at |
| `calendar_events` | Economic calendar | date, impact |
| `audit_log` | Security and operations audit trail | timestamp, event_type |

---

## Security Framework Architecture

```
+------------------------------------------------------------------+
|                     SECURITY FRAMEWORK                            |
+------------------------------------------------------------------+
|                                                                    |
|  LAYER 1: API BOUNDARY (Runtime)                                  |
|  +------------------------------------------------------------+  |
|  | input_validator.py                                          |  |
|  | - validate_instrument() : whitelist check (12 keys)         |  |
|  | - validate_date_range() : max 20yr, format, ordering        |  |
|  | - sanitize_search_query() : strip injection chars, 200 max  |  |
|  +------------------------------------------------------------+  |
|  | auth.py (APIKeyMiddleware)                                  |  |
|  | - X-API-Key header on /api/v1/* routes                      |  |
|  | - Public mode if SCALP_API_KEY not set                      |  |
|  +------------------------------------------------------------+  |
|                                                                    |
|  LAYER 2: LLM EVALUATION (Batch)                                  |
|  +------------------------------------------------------------+  |
|  | Promptfoo Configs (6 YAML files)                            |  |
|  | - red-team.yaml       : 30 tests, 8 attack categories      |  |
|  | - injection.yaml      : 50 tests, 7 categories             |  |
|  | - hallucination.yaml  : 38 tests, 6 categories             |  |
|  | - compliance.yaml     : 34 tests, 6 regulatory domains     |  |
|  | - pii.yaml            : PII exposure tests                  |  |
|  | - jailbreak.yaml      : Jailbreak-specific tests            |  |
|  | - benchmark.yaml      : Performance benchmarks              |  |
|  +------------------------------------------------------------+  |
|  | Custom Grader (security_grader.py)                          |  |
|  | - 5 weighted dimensions                                     |  |
|  | - prompt_leak (1.0) + instruction_following (1.0)           |  |
|  | - pii_exposure (1.5) + harmful_content (2.0)                |  |
|  | - jailbreak_success (1.5)                                   |  |
|  | - Pass threshold: weighted avg >= 0.7 AND no dim < 0.5      |  |
|  +------------------------------------------------------------+  |
|                                                                    |
|  LAYER 3: AUDIT TRAIL (Runtime)                                   |
|  +------------------------------------------------------------+  |
|  | audit_log.py                                                |  |
|  | - log_event(event_type, details) -> audit_log table         |  |
|  | - Never crashes caller (exception-safe)                     |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
```

---

## Agent Prompt Library Organization

```
agents/
  _schema.json              # JSON Schema (2020-12) for validation
  _template.md              # Agent authoring template

  01-development/           # 30+ agents: coder, reviewer, tester,
                            # debugger, refactorer, specialists
                            # (TypeScript, Python, Rust, Go, React,
                            # Next.js, Tailwind, GraphQL, WebSocket)

  02-security/              # 25+ agents: auditor, pen tester,
                            # threat modeler, compliance checker

  03-trading/               # 35+ agents: COT analyst, SMC trader,
                            # risk manager, portfolio optimizer

  04-data-ml/               # 30+ agents: data scientist, ML engineer,
                            # NLP, computer vision, RAG architect,
                            # prompt engineer, LLM fine-tuner

  05-devops-infra/          # 25+ agents: CI/CD, Docker, Kubernetes,
                            # Terraform, SRE

  06-seo-marketing/         # 20+ agents: SEO auditor, content writer

  07-product-design/        # 20+ agents: UX researcher, PM, A/B tester

  08-project-management/    # 15+ agents: sprint planner, agile coach,
                            # scrum master, OKR tracker, velocity analyst

  09-writing-docs/          # 20+ agents: technical writer, API docs,
                            # tutorial creator

  10-orchestration/         # 25+ agents: swarm coordinator, router

  11-domain-specific/       # 35+ agents: healthcare, legal, finance

  12-meta-agents/           # 30+ agents: self-improver, evaluator
```

### Agent Schema (from `_schema.json`)

Every agent prompt file must include YAML frontmatter with these required fields:

```yaml
---
name: "agent-name"               # Unique identifier
description: "20+ char desc"     # When to use this agent
domain: "development"            # One of 12 domains
complexity: "intermediate"       # basic | intermediate | advanced | expert
model: "sonnet"                  # haiku | sonnet | opus
tools: [Read, Grep, Glob]       # Available tools
tags: [tag1, tag2]               # Searchable tags
version: "1.0.0"                 # Semantic version
related_agents: [agent1]         # Optional: related agents
---
```

### Market Analysis Prompt Architecture

The `src/agents/prompts/market_analysis/` directory contains structured YAML prompt definitions:

| File | Prompts | Schedule | Model |
|---|---|---|---|
| `trend.yaml` | 24 daily trend + 12 weekly trend + 2 cross-instrument | daily/weekly | haiku/sonnet |
| `smc_structure.yaml` | SMC structure analysis prompts | every run | sonnet |
| `levels.yaml` | Level detection and tagging prompts | every run | haiku |
| `regime.yaml` | Macro regime classification prompts | every run | sonnet |
| `intermarket.yaml` | Cross-market correlation prompts | daily | sonnet |

Each prompt defines:
- `input_schema`: Required data inputs (e.g., daily_ohlc_200, sma200, atr_d14)
- `output_schema`: Expected JSON output structure (e.g., trend, strength, key_levels)
- `prompt`: The actual instruction text with instrument-specific context

---

## Data Flow Diagrams

### Pipeline Run (4x daily)

```
07:45 CET  +---------+
12:30 CET  | GitHub   |   Cron triggers
14:15 CET  | Actions  |---+
17:15 CET  +---------+   |
                          v
              +-----------------------+
              | 1. Fetch COT Data     |  CFTC.gov (weekly, cached)
              +-----------------------+
                          |
              +-----------------------+
              | 2. Fetch Prices       |  Twelvedata -> Stooq -> Yahoo
              |    (12 instruments)   |  + Finnhub overlay
              +-----------------------+
                          |
              +-----------------------+
              | 3. Fetch Fundamentals |  FRED (GDP, CPI, NFP, rates)
              +-----------------------+
                          |
              +-----------------------+
              | 4. Fetch Calendar     |  ForexFactory (upcoming events)
              +-----------------------+
                          |
              +-----------------------+
              | 5. Run Analysis       |  SMC + Levels + Scoring
              |    (per instrument)   |  for each of 12 instruments
              +-----------------------+
                          |
              +-----------------------+
              | 6. Build Setups       |  L2L setups with structural SL
              +-----------------------+
                          |
              +-----------------------+
              | 7. Score & Grade      |  12-point confluence scoring
              +-----------------------+
                          |
         +----------------+----------------+
         |                |                |
         v                v                v
+-------------+  +----------------+  +------------------+
| DB: signals |  | JSON: static   |  | Push: Telegram   |
| DB: macro   |  | for dashboard  |  | Push: Discord    |
+-------------+  +----------------+  +------------------+
         |                |
         v                v
+-------------+  +------------------+
| API Server  |  | GitHub Pages     |
| (FastAPI)   |  | (Frontend)       |
+-------------+  +------------------+
```

### API Request Flow

```
Client Request
      |
      v
+------------------+
| CORS Middleware   |  Allow all origins (dev mode)
+------------------+
      |
      v
+------------------+
| APIKeyMiddleware  |  Check X-API-Key if SCALP_API_KEY set
+------------------+
      |
      v
+------------------+
| FastAPI Router    |  Route to correct handler
+------------------+
      |
      +-----> /health          -> health.py -> DB latest signal timestamp
      +-----> /metrics         -> health.py -> DB row counts
      +-----> /api/v1/signals  -> signals.py -> DB query with filters
      +-----> /api/v1/cot      -> cot.py -> DB or data/combined/latest.json
      +-----> /api/v1/macro    -> macro.py -> DB or data/macro/latest.json
      +-----> /api/v1/instruments -> instruments.py -> config/instruments.yaml
      +-----> /api/v1/webhook  -> webhook.py -> audit log + ack
```

---

## API Endpoints

### Health & Metrics

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status, version, last_run timestamp |
| GET | `/metrics` | Row counts: signals, prices, COT positions |

### Signals

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/api/v1/signals` | `grade`, `timeframe`, `min_score`, `direction`, `active_only`, `instrument`, `limit` | List signals with filters |
| GET | `/api/v1/signals/{key}` | -- | Latest signal for instrument |

### COT Data

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/api/v1/cot` | -- | All latest COT positions |
| GET | `/api/v1/cot/{symbol}/history` | `start`, `end`, `report_type` | Historical COT for symbol |
| GET | `/api/v1/cot/summary` | -- | Top movers and positioning extremes |

### Macro Data

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/macro` | Full macro panel (Dollar Smile, VIX, conflicts) |
| GET | `/api/v1/macro/indicators` | Subset: HYG, TIP, TNX, IRX, Copper, EEM |

### Instruments

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/instruments` | All 12 tracked instruments |
| GET | `/api/v1/instruments/{key}` | Single instrument + latest price |

### Webhook

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/webhook/push-alert` | Receive push-alert payloads (v1 compat) |

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | >= 3.11 |
| Web Framework | FastAPI | >= 0.100 |
| ASGI Server | Uvicorn | >= 0.20 |
| ORM | SQLAlchemy | >= 2.0 |
| Database | SQLite | (bundled) |
| Validation | Pydantic | >= 2.0 |
| Templating | Jinja2 | >= 3.0 |
| Scheduling | APScheduler | >= 3.10 |
| Config | PyYAML | >= 6.0 |
| Security Testing | Promptfoo | >= 0.97.0 |
| Linting | Ruff | >= 0.1 |
| Type Checking | Mypy | >= 1.0 |
| Testing | Pytest | >= 7.0 |
| Dep Auditing | pip-audit | >= 2.0 |
| Build System | Hatchling | latest |
