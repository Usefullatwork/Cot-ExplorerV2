5-Question context recovery test. Use when context feels degraded or after multiple compactions.

## The 5 Questions

Answer each question. If you cannot answer confidently, STOP and research before continuing.

1. **Where am I?** — What branch? What directory? What's the repo state?
2. **Where am I going?** — What's the current goal? Read `.planning/task_plan.md`
3. **What's the goal?** — Why are we doing this? What problem does it solve?
4. **What have I learned?** — Read `.planning/findings.md` and `.planning/progress.md`
5. **What's done?** — Which tasks are completed? Which remain?

## Recovery Steps

1. Run `bash scripts/session-catchup.sh` if it exists
2. Read all 3 `.planning/` files
3. Answer the 5 questions above
4. If any answer is "I don't know" — ask the user before proceeding
5. If all 5 are answered — state next action and continue

## When to Suggest Fresh Session

If after recovery you still feel uncertain about the plan, suggest:
"Context may be too degraded. Consider starting a fresh session with /resume."
