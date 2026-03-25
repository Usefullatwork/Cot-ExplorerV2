---
description: Create comprehensive planning documentation for a feature
argument-hint: "<feature-slug>"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** parse the user input to extract the feature slug (the folder name in `rpi/`).

## Purpose

Creates comprehensive planning documentation for a feature request.

**Prerequisites**: `rpi/{feature-slug}/research/RESEARCH.md` exists with GO recommendation
**Output**: `rpi/{feature-slug}/plan/` (pm.md, ux.md, eng.md, PLAN.md)
**RPI Step**: 3 of 4 (Describe -> Research -> **Plan** -> Implement)

## Phases

### Phase 0: Load Context
1. Read `rpi/{feature-slug}/research/RESEARCH.md`
2. Verify GO recommendation
3. Load CLAUDE.md project constitution

### Phase 1: Understand Requirements
- Parse feature scope from research report
- Identify affected components
- Research existing patterns in codebase

### Phase 2: Analyze Technical Requirements
- Review component architecture
- Identify dependencies and integration points
- Assess technical risks

### Phase 3: Design Architecture
**Agent**: senior-software-engineer
- High-level architecture, API contracts, DB schema changes, testing strategy

### Phase 4: Break Down Tasks
- 3-5 logical phases, each delivering testable functionality
- Task breakdown with complexity estimates
- Success criteria per phase

### Phase 5: Generate Documentation
**Agents**: product-manager (pm.md), ux-designer (ux.md), senior-software-engineer (eng.md), documentation-analyst-writer (PLAN.md)

## Output Files
- `rpi/{feature-slug}/plan/pm.md` — Product requirements
- `rpi/{feature-slug}/plan/ux.md` — UX design
- `rpi/{feature-slug}/plan/eng.md` — Technical specification
- `rpi/{feature-slug}/plan/PLAN.md` — Phased implementation roadmap

## Next Steps
Run `/rpi:implement "{feature-slug}"` to execute phased implementation.

## Post-Completion

> Run `/compact` to free context for implementation.
