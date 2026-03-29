# 3-Strike Error Protocol

When a tool call, test, or build fails:

## Strike 1: Diagnose & Fix
- Read the error message carefully
- Identify root cause (not just symptoms)
- Apply a targeted fix
- Re-run to verify

## Strike 2: Alternative Approach
- The first fix didn't work — do NOT retry the same thing
- Step back and consider a different approach
- Check if the problem is upstream (wrong file, wrong assumption, missing dependency)
- Apply the alternative and verify

## Strike 3: STOP
- Two attempts failed — continuing will waste tokens and context
- Log the issue to `.planning/progress.md` with:
  - What was attempted
  - What error occurred each time
  - What you think the root cause might be
- Ask the user for guidance before proceeding

## Hard Rules
- NEVER retry the exact same approach twice
- NEVER ignore test failures and move on
- NEVER suppress errors to make tests pass (unless the error itself is the bug being fixed)
- If you catch yourself in a retry loop, invoke Strike 3 immediately
