# Contributing to Cot-ExplorerV2

## Development Setup

### Prerequisites

- **Python 3.11+** (3.13 recommended)
- **Node.js 18+** (for frontend and tooling)
- **Git**

### Installation

```bash
git clone https://github.com/Usefullatwork/Cot-ExplorerV2.git
cd Cot-ExplorerV2

# Backend
pip install -e ".[dev]"
alembic upgrade head

# Frontend
cd frontend && npm install
```

### Environment

Copy the example env vars (never commit real keys):

```bash
export COT_API_KEY="dev-key"
export FRED_API_KEY="your-fred-key"
```

## Running Tests

### Python (pytest)

```bash
# All tests (603+ test functions)
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Single file
pytest tests/unit/test_scoring.py -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

### Frontend (Vitest)

```bash
cd frontend
npm test
```

## Code Style

### Python

- **Linter/Formatter:** [Ruff](https://docs.astral.sh/ruff/) (`ruff check src/ tests/`)
- **Line length:** 120 characters
- **Target version:** Python 3.11
- **Rules:** E, F, W, I (pycodestyle errors/warnings, pyflakes, isort)
- **Type hints:** Required on all public functions. Check with `mypy src/`.
- **Imports:** Use absolute imports from `src.` (e.g., `from src.analysis.scoring import ...`)

### JavaScript

- **Frontend:** Vanilla JS (no framework), ES modules
- **Tests:** Vitest + @testing-library/dom

### General

- Keep files under 500 lines. Extract modules when approaching the limit.
- Use descriptive variable/function names. No abbreviations except well-known ones (e.g., SMC, COT, BOS).
- Every new module needs corresponding tests.

## Project Structure

- `src/` -- All Python source code (never add source files to the project root)
- `tests/unit/` -- Unit tests (mock external dependencies)
- `tests/integration/` -- Integration tests (may use real DB, test client)
- `tests/fixtures/` -- Shared test data
- `frontend/src/` -- Frontend source code
- `scripts/` -- One-off utilities (migration, validation)
- `config/` -- YAML configuration files
- `docs/` -- Architecture and reference documentation

Root-level Python files (`fetch_cot.py`, `fetch_all.py`, etc.) are **thin wrappers** that import from `src/trading/core/`. Do not add logic to them.

## Pull Request Process

1. **Branch** from `main` with a descriptive name (e.g., `feat/backtest-sharpe-ratio`, `fix/cot-date-parsing`)
2. **Write tests** for new code. Aim for the same coverage level as existing modules.
3. **Run the full test suite** before pushing:
   ```bash
   pytest
   cd frontend && npm test
   ```
4. **Lint and type-check:**
   ```bash
   ruff check src/ tests/
   mypy src/
   ```
5. **Keep commits atomic** -- one logical change per commit.
6. **Write clear commit messages** using conventional commits:
   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code restructure (no behavior change)
   - `test:` adding/updating tests
   - `docs:` documentation only
   - `chore:` tooling, config, dependencies

## Database Migrations

When changing `src/db/models.py`:

```bash
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

Review the generated migration file in `alembic/versions/` before committing.

## Adding a New Data Provider

1. Create `src/data/providers/your_provider.py` extending `BaseProvider` from `src/data/providers/base.py`
2. Add it to the failover chain in `src/data/price_router.py`
3. Write unit tests in `tests/unit/test_your_provider.py`
4. Add rate limit config to `src/data/rate_limiter.py` if needed
5. Document the provider in the Data Sources table in `README.md`

## Adding a Backtest Strategy

1. Create `src/trading/backtesting/strategies/your_strategy.py`
2. Implement the strategy interface matching existing strategies (see `cot_momentum.py`)
3. Write tests in `tests/integration/test_backtest_engine.py`
4. Register the strategy in `src/api/routes/backtests.py` if it should be API-accessible
