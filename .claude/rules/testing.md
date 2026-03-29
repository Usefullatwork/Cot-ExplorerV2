# Testing Rules

## Test Runners
- **Python**: `pytest tests/ -v --tb=short`
- **Frontend**: `cd frontend && npx vitest --run`
- **Lint**: `ruff check src/ tests/`
- **Types**: `mypy src/`

## When Tests Are Required
- Every new function or endpoint gets at least one test
- Every bug fix gets a regression test BEFORE the fix (TDD)
- Every route handling user data gets auth tests (401/403)

## Test Quality
- Test behavior, not implementation (assert outputs, not internal calls)
- One assertion concept per test (multiple expects are fine if testing one behavior)
- Test names describe the scenario: `should return 401 when token is missing`
- No `test.skip` without a TODO comment explaining why

## Project-Specific
- No mocking of pure functions in `src/analysis/` — test with real data
- Pytest for Python, Vitest for JS (never mix)
- Realistic fixture data, deterministic (seeded random)

## Known Limitations
- PGlite WASM crashes under parallel suites — known, not regression
