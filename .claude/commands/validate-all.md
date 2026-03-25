---
description: Run tests, lint, and build verification in sequence
allowed-tools: Bash, Read
---

Run full validation suite for Cot-ExplorerV2:

## Step 1: Tests
```bash
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2 && python -m pytest tests/ -v --tb=short
```

## Step 2: Lint (if ruff installed)
```bash
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2 && python -m ruff check src/ --select E,W,F
```

## Step 3: Type Check (if mypy installed)
```bash
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2 && python -m mypy src/ --ignore-missing-imports
```

## Step 4: Frontend Build
```bash
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2\frontend && npm run build
```

Report pass/fail for each step. If any step fails, continue to remaining steps and report all results.
