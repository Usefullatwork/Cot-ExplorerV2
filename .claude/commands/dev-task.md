Dispatch a single development task to a fresh subagent with isolated context.

## Usage

`/dev-task "description of the task"`

$ARGUMENTS

## How It Works

1. Read `CLAUDE.md` for project context
2. Read `.planning/task_plan.md` if it exists (for current plan awareness)
3. Spawn a subagent with ONLY the task description + project context
4. The subagent gets fresh context (no accumulated pollution from this session)
5. Wait for result, then verify:
   - Did the subagent complete the task?
   - Do tests still pass?
   - Any unexpected side effects? (`git diff --stat`)

## Subagent Instructions Template

You are working on this project. Read CLAUDE.md first for project context.

YOUR TASK: [task description]

RULES:
- Read relevant files before editing
- Run tests after changes
- Stage changed files by name (not git add .)
- Do not modify files outside the scope of this task

## After Completion

Report: task description, files changed, test results, any issues found.
