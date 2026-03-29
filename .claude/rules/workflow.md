# Workflow Rules

## Multi-File Changes (3+ files)
1. Use the design-first skill — mandatory
2. Read ALL target files first (read-only pass)
3. Write design to `.planning/task_plan.md`
4. Present design to user, wait for approval
5. **No code changes until user approves**
6. Execute one file at a time, verify after each

## Single-File Changes
1. Read the file
2. Make the change
3. Run relevant tests
4. Done

## Bug Fixes
1. Write a failing test that reproduces the bug
2. Fix the bug (minimum change needed)
3. Verify the test passes
4. Check no other tests broke

## Refactors
1. Ensure full test coverage exists first
2. Run tests before starting (baseline)
3. Make changes incrementally
4. Run tests after each increment
5. If tests break, revert the last increment and try differently

## Project-Specific
- Pure functions in `src/analysis/` must remain side-effect-free
