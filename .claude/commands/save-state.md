Save current session state to disk before /compact.

## Steps

1. Read the current `.planning/task_plan.md` and update it with:
   - Which tasks are done (check them off)
   - Which task is currently in progress
   - Any new tasks discovered during execution

2. Read `.planning/findings.md` and append any new:
   - Architecture discoveries
   - Design decisions made
   - File dependencies identified

3. Read `.planning/progress.md` and append a timestamped summary:
   - What was accomplished since last save
   - Current test status (pass/fail counts)
   - Any errors or blockers encountered
   - What the next step should be

4. Run `git status` and note any uncommitted changes

5. Confirm: "State saved. Safe to /compact now."
