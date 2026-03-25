---
description: Run the full pytest suite and report results
allowed-tools: Bash, Read
---

Run the Cot-ExplorerV2 test suite:

```bash
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2 && python -m pytest tests/ -v --tb=short
```

Report:
1. Total tests run
2. Passed / Failed / Errors / Skipped counts
3. If failures: list failed test names and first line of error
4. Duration
