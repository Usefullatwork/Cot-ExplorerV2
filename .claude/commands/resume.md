Restore context after /compact or fresh session start.

## Steps

1. Read CLAUDE.md first for project context
2. Read `.planning/task_plan.md` — understand the goal, phases, and current progress
3. Read `.planning/findings.md` — restore architecture context and decisions
4. Read `.planning/progress.md` — understand what happened recently and what's next
5. Run `git status` and `git log --oneline -5` — understand current repo state
6. Run `bash scripts/session-catchup.sh` if it exists — get system health snapshot

## Output

Summarize in this format:

RESUMING SESSION
Goal: [from task_plan]
Progress: [X/Y tasks done]
Last action: [from progress log]
Next step: [from task_plan]
Git state: [branch, uncommitted changes]
Health: [test status if available]

Then proceed with the next unchecked task from the plan.
