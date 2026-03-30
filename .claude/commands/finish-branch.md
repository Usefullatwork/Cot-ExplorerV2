Pre-merge checklist for the current feature branch.

## Steps

1. **Run all tests:**
   ```bash
   pytest tests/ -v --tb=short
   cd frontend && npx vitest --run
   ruff check src/
   mypy src/
   ```

2. **Check for debug artifacts:**
   - Search for `console.log` in frontend source files
   - Search for `print(` debug statements in Python source files
   - Search for `TODO`, `FIXME`, `HACK`, `XXX` in source files

3. **Verify build:**
   ```bash
   cd frontend && npm run build
   ```

4. **Show summary:**
   - Branch name and commit count vs main
   - Files changed (`git diff --stat main`)
   - Test results (pass/fail counts)
   - Any warnings found in step 2

5. **Present options:**

   Only if ALL tests pass and build succeeds:

   - **A) Push for PR** — `git push -u origin <branch>` then `gh pr create`
   - **B) Keep working** — Stay on branch, list remaining issues

   If tests fail or build broken:
   - Show failures and suggest fixes
   - Only offer option B
