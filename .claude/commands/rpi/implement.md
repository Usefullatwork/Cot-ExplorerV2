---
description: Execute phased implementation with validation gates
argument-hint: "<feature-slug> [--phase N] [--validate-only]"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** parse the user input to extract the feature slug.

## Purpose

Executes phased implementation based on planning documentation.

**Prerequisites**: `rpi/{feature-slug}/plan/PLAN.md` exists
**Output**: `rpi/{feature-slug}/implement/IMPLEMENT.md`
**RPI Step**: 4 of 4 (Describe -> Research -> Plan -> **Implement**)

## Flags
- `--phase N`: Execute specific phase (1-8)
- `--validate-only`: Only validate, don't implement
- `--skip-validation`: Skip validation gate (use with caution)

## Phase Implementation Loop

For each phase in PLAN.md:

### Step 1: Code Discovery
**Agent**: Explore (subagent_type="Explore")
- Understand existing code before changing it

### Step 2: Implementation
**Agent**: senior-software-engineer
- Implement phase deliverables following discovery context

### Step 3: Self-Validation
- Run linter: `ruff check src/`
- Run tests: `python -m pytest tests/ -v --tb=short`
- Verify build

### Step 4: Code Review
**Agent**: code-reviewer
- Security, correctness, maintainability review

### Step 5: User Validation Gate
**STOP** and present deliverables checklist, files changed, test results, review verdict. Wait for user PASS/CONDITIONAL PASS/FAIL.

### Step 6: Documentation Update
- Update PLAN.md checkboxes
- Append to `rpi/{feature-slug}/implement/IMPLEMENT.md`

## Phase Status
- `[ ]` Not Started
- `[~]` In Progress
- `[x]` Validated (PASS)
- `[!]` Conditional Pass
- `[-]` Failed Validation

## Error Handling
- Implementation failure: max 2 attempts, then ask user
- Test failure: diagnose cause, fix, re-run
- Agent failure: retry once, proceed without if still failing

## Quality Gates

**Per-Phase**: All deliverables implemented, linting passes, tests pass, build succeeds, code review passed, user validation received.

**Final**: All phases validated, no failing tests, full build success, PR notes generated.

## Post-Completion

> Run `/compact` to free context.
