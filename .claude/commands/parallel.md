Dispatch multiple independent tasks to parallel subagents.

## Usage

`/parallel "task1" "task2" "task3"`

$ARGUMENTS

## How It Works

1. Parse the argument into separate task descriptions
2. Verify tasks are truly independent (no shared file modifications)
3. Spawn one subagent per task, all in parallel with `run_in_background: true`
4. Each subagent gets:
   - Fresh context (CLAUDE.md + task description only)
   - Isolated scope (only modify files relevant to their task)
5. Wait for ALL results to return
6. Verify each result:
   - Task completed successfully?
   - No conflicting file changes across agents?
   - Tests still pass?

## Conflict Detection

Before spawning, check for overlapping files:
- If two tasks might edit the same file, run them sequentially instead
- If tasks are in different directories (backend/ vs frontend/), they're safe to parallelize

## After Completion

Report summary:

PARALLEL RESULTS (N tasks)
1. [task] — OK/FAILED — [files changed]
2. [task] — OK/FAILED — [files changed]
Conflicts: none / [list]
Tests: passing / failing
