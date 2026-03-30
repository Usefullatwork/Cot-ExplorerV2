---
name: design-first
description: Mandatory design gate for changes touching 3+ files. Enforces read-first, plan-first, approve-first workflow to prevent wrong-approach rework.
---

# Design-First Gate

This skill activates automatically when a task will modify 3 or more files.

## Phase 1: Research (Read-Only)

Read ALL files that will be modified. Do not edit anything yet.

For each file, note:
- Current structure and patterns
- How it connects to other files being changed
- Any tests that cover this file

Write findings to `.planning/findings.md`.

## Phase 2: Design

Write the implementation plan to `.planning/task_plan.md`:
- Goal (1 sentence)
- Files to modify (with specific changes per file)
- Order of changes (dependencies first)
- Verification steps (which tests to run, what to check)
- Rollback plan (how to undo if it goes wrong)

## Phase 3: Approval Gate

Present the design to the user:

DESIGN REVIEW
Goal: [goal]
Files: [count] files to modify
Changes:
1. [file] — [what changes]
2. [file] — [what changes]
Tests: [which tests verify this]
Risk: [low/medium/high]

Proceed? (y/n)

**HARD GATE: Do NOT write any code until the user approves.**

## Phase 4: Execute

After approval:
1. Execute changes one file at a time
2. Run tests after each file change
3. If tests fail, stop and diagnose (do not continue to next file)
4. Update `.planning/progress.md` after each step

## Phase 5: Verify

After all changes:
1. Run full test suite for affected area
2. Verify build succeeds
3. Compare result against the approved design
4. Report any deviations

## Project-Specific
- Pure functions in `src/analysis/` must remain side-effect-free
