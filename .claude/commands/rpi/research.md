---
description: Research and analyze feature viability — GO/NO-GO decision gate
argument-hint: "<feature-slug>"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** parse the user input to extract the feature slug (the folder name in `rpi/`).

## Purpose

Performs comprehensive research and analysis of feature requests **before** planning. Acts as a GO/NO-GO gate.

**Prerequisites**: `rpi/{feature-slug}/REQUEST.md` exists
**Output**: `rpi/{feature-slug}/research/RESEARCH.md`
**RPI Step**: 2 of 4 (Describe -> **Research** -> Plan -> Implement)

## Phases

### Phase 0: Load Context
1. Read `rpi/{feature-slug}/REQUEST.md`
2. Read `CLAUDE.md` for project constitution
3. Synthesize context for agents

### Phase 1: Parse Feature Request
**Agent**: requirement-parser
- Extract: name, type, component, complexity, requirements, constraints

### Phase 2: Product Analysis
**Agent**: product-manager
- Analyze: user value, market fit, product vision, constitutional alignment

### Phase 2.5: Technical Discovery
**Agent**: Explore (via Agent tool with subagent_type="Explore")
- Investigate: existing implementation, integration points, reusable components, constraints from code

### Phase 3: Technical Feasibility
**Agent**: senior-software-engineer
- Assess: approach, complexity, dependencies, tech debt, risks

### Phase 4: Strategic Assessment
**Agent**: technical-cto-advisor
- Synthesize: overall assessment, risk vs reward, build/buy/defer/decline

### Phase 5: Generate Report
**Agent**: documentation-analyst-writer
- Create `rpi/{feature-slug}/research/RESEARCH.md` with all findings

## Completion

Report: **Decision** (GO/NO-GO/CONDITIONAL/DEFER), **Confidence**, **Rationale**, **Next Steps**

If GO: `/rpi:plan "{feature-slug}"`

## Post-Completion

> Run `/compact` to free context for next steps.
