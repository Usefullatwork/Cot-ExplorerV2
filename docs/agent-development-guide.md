# Agent Development Guide -- Cot-ExplorerV2

Last updated: 2026-03-25

This guide covers how to create, validate, and contribute agent prompts to the Cot-ExplorerV2 library of 310+ agent prompts across 12 domains.

---

## Table of Contents

1. [Schema Reference](#schema-reference)
2. [Quality Standards](#quality-standards)
3. [Domain-Specific Writing Guidelines](#domain-specific-writing-guidelines)
4. [How to Validate Agents](#how-to-validate-agents)
5. [Contribution Workflow](#contribution-workflow)

---

## Schema Reference

Every agent prompt file is a Markdown file with YAML frontmatter. The frontmatter must validate against `agents/_schema.json`.

### Required Fields

| Field | Type | Description | Example |
|---|---|---|---|
| `name` | string | Unique agent identifier. Lowercase, hyphenated. | `"code-reviewer"` |
| `description` | string (min 20 chars) | One-line description of when to use this agent. Must clearly state the agent's purpose. | `"Reviews pull requests for code quality, security vulnerabilities, and adherence to team conventions"` |
| `domain` | enum | One of 12 domains (see Domain List below). | `"development"` |
| `complexity` | enum | `basic`, `intermediate`, `advanced`, or `expert`. Determines the minimum model tier. | `"intermediate"` |
| `model` | enum | `haiku`, `sonnet`, or `opus`. Recommended model for this agent. | `"sonnet"` |
| `tools` | array of strings | Tools the agent needs access to. | `["Read", "Grep", "Glob", "Edit"]` |
| `tags` | array of strings | Searchable tags for discovery. | `["code-review", "pull-request", "quality"]` |
| `version` | string | Semantic version of this agent prompt. | `"1.0.0"` |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| `related_agents` | array of strings | Names of agents that complement this one. |

### Domain List

| Domain Value | Directory | Description |
|---|---|---|
| `development` | `01-development/` | Software development: coding, review, testing, debugging |
| `security` | `02-security/` | Security auditing, pen testing, threat modeling |
| `trading` | `03-trading/` | Trading analysis, risk management, portfolio optimization |
| `data-ml` | `04-data-ml/` | Data science, ML engineering, NLP, computer vision |
| `devops` | `05-devops-infra/` | CI/CD, Docker, Kubernetes, Terraform, SRE |
| `seo` | `06-seo-marketing/` | SEO, content marketing, analytics |
| `product` | `07-product-design/` | UX research, product management, A/B testing |
| `project-mgmt` | `08-project-management/` | Sprint planning, agile coaching, project tracking |
| `writing` | `09-writing-docs/` | Technical writing, API documentation, tutorials |
| `orchestration` | `10-orchestration/` | Multi-agent coordination, routing, swarm management |
| `domain-specific` | `11-domain-specific/` | Healthcare, legal, finance, education |
| `meta` | `12-meta-agents/` | Self-improvement, evaluation, prompt optimization |

### Complexity-to-Model Mapping

| Complexity | Recommended Model | Use Case |
|---|---|---|
| `basic` | `haiku` | Simple transforms, classification, formatting. Low reasoning required. |
| `intermediate` | `sonnet` | Standard development tasks, analysis, code generation. Moderate reasoning. |
| `advanced` | `sonnet` or `opus` | Complex architecture, security analysis, multi-step reasoning. |
| `expert` | `opus` | Novel research, complex refactoring, nuanced domain expertise. |

### Tool Reference

Common tools available to agents:

| Tool | Purpose |
|---|---|
| `Read` | Read file contents |
| `Write` | Create or overwrite files |
| `Edit` | Make targeted edits to existing files |
| `Grep` | Search file contents with regex |
| `Glob` | Find files by name pattern |
| `Bash` | Execute shell commands |
| `WebSearch` | Search the web for current information |
| `WebFetch` | Fetch content from a URL |

---

## Quality Standards

### Prompt Structure

Every agent prompt should follow the template in `agents/_template.md`:

```markdown
---
name: agent-name
description: One-line description of when to use this agent
domain: development
complexity: intermediate
model: sonnet
tools: [Read, Grep, Glob, Edit, Write, Bash]
tags: [tag1, tag2]
related_agents: [related1, related2]
version: "1.0.0"
---

# Agent Name

## Role
You are a [role description]. Your expertise includes [areas].

## Core Capabilities
1. [Capability 1]
2. [Capability 2]
3. [Capability 3]

## Input Format
- [What the agent expects as input]

## Output Format
[Structured output format]

## Decision Framework
[How the agent makes decisions]

## Example Usage
1. "[Example prompt 1]"
2. "[Example prompt 2]"

## Constraints
- [Constraint 1]
- [Constraint 2]
```

### Content Quality Checklist

Before submitting an agent prompt, verify:

- [ ] **Frontmatter validates** against `_schema.json`
- [ ] **Description is actionable** -- starts with a verb, clearly states when to use the agent
- [ ] **Role section is specific** -- not generic "you are helpful"; states concrete expertise
- [ ] **Capabilities are measurable** -- each capability could be tested with a concrete task
- [ ] **Input format is clear** -- a user reading this knows exactly what to provide
- [ ] **Output format is structured** -- defines the expected shape of the response
- [ ] **Decision framework exists** -- explains HOW the agent reasons, not just WHAT it does
- [ ] **Examples are realistic** -- 2-3 actual prompts a user would send
- [ ] **Constraints are explicit** -- what the agent should NOT do
- [ ] **Model selection is justified** -- haiku for simple tasks, opus for expert reasoning
- [ ] **Tools are minimal** -- only request tools the agent actually needs

### Naming Conventions

- **File name:** Lowercase, hyphenated. Matches the `name` field. Example: `code-reviewer.md`
- **Agent name:** Lowercase, hyphenated. Unique across all domains. Example: `code-reviewer`
- **Tags:** Lowercase, hyphenated. Use established tags where possible.
- **Version:** Semantic versioning. Start at `1.0.0`. Bump minor for capability additions, major for breaking changes.

### Description Quality

Good descriptions:
- "Reviews Python code for PEP 8 compliance, type safety, and common anti-patterns"
- "Generates Terraform modules for AWS infrastructure with security best practices"
- "Analyzes COT positioning data and identifies institutional flow reversals"

Bad descriptions:
- "A helpful coding assistant" (too vague)
- "Does stuff with code" (not actionable)
- "AI agent for development" (no specific use case)

---

## Domain-Specific Writing Guidelines

### Development Agents (01-development/)

- Specify language/framework expertise explicitly (e.g., "TypeScript + React", not just "frontend")
- Include coding standards the agent follows (e.g., "follows PEP 8", "uses ESLint recommended rules")
- Define error handling expectations
- Specify whether the agent generates tests alongside code
- Reference specific tools: linters, formatters, type checkers

### Security Agents (02-security/)

- Define the threat model scope (web app, API, infrastructure, LLM)
- Reference specific vulnerability databases (CVE, OWASP Top 10)
- Include severity classification in output format (Critical/High/Medium/Low)
- Specify compliance frameworks (GDPR, SOC2, HIPAA, Norwegian healthcare law)
- Define what counts as a false positive

### Trading Agents (03-trading/)

- Always include risk disclaimers in constraints
- Specify data requirements precisely (OHLC timeframe, lookback period)
- Define output confidence levels (0-1 scale)
- Reference specific indicators with parameters (e.g., "ATR(14)", "SMA(200)")
- Include Norwegian market terminology where appropriate (the platform uses Norwegian labels)
- Never fabricate data -- this must be an explicit constraint for every trading agent

### Data & ML Agents (04-data-ml/)

- Specify input data format requirements (CSV, Parquet, JSON, DataFrame)
- Define evaluation metrics for ML tasks (accuracy, F1, RMSE, etc.)
- Include data quality checks in the workflow
- Specify computational requirements (GPU needed? Batch size constraints?)
- Reference specific libraries (scikit-learn, PyTorch, pandas)

### Project Management Agents (08-project-management/)

- Use agile terminology consistently (sprint, story point, velocity, burndown)
- Define the methodology context (Scrum, Kanban, SAFe)
- Include stakeholder communication templates in output format
- Specify what "done" means for each capability

### Domain-Specific Agents (11-domain-specific/)

- Always reference applicable laws and regulations by name
- Include jurisdiction (e.g., "Norwegian law" not just "the law")
- Define professional scope of practice boundaries
- Include mandatory disclaimers (e.g., "not medical/legal advice")
- Reference authoritative sources for claims

---

## How to Validate Agents

### Schema Validation

Run the validation script to check all agent prompts against `_schema.json`:

```bash
python scripts/validate-agents.py
```

This script:
1. Scans all `.md` files in `agents/` subdirectories
2. Extracts YAML frontmatter from each file
3. Validates against `agents/_schema.json`
4. Reports any validation errors (missing fields, wrong types, invalid enum values)

### Manual Validation Checklist

For each agent, verify:

1. **Frontmatter parses:** YAML between `---` markers is valid
2. **Required fields present:** name, description, domain, complexity, model, tools, tags, version
3. **Domain is valid:** One of the 12 enum values
4. **Complexity is valid:** basic, intermediate, advanced, or expert
5. **Model is valid:** haiku, sonnet, or opus
6. **Description length:** At least 20 characters
7. **File location:** Agent is in the correct domain directory

### Building the Agent Index

Generate a searchable catalog of all agents:

```bash
python scripts/build-agent-index.py
```

This produces a JSON index file that maps agent names to their metadata, enabling programmatic agent discovery and routing.

### Testing an Agent Prompt

To functionally test an agent, use it in a conversation and verify:

1. The agent stays within its defined role
2. Output matches the specified format
3. The agent uses only the tools listed in its frontmatter
4. Constraints are respected
5. Example usage prompts produce reasonable responses

---

## Contribution Workflow

### Adding a New Agent

1. **Choose the domain.** Determine which of the 12 categories your agent fits into.

2. **Check for duplicates.** Search existing agents to ensure no overlap:
   ```bash
   # Search by name
   ls agents/01-development/

   # Search by tag
   grep -r "tags:.*code-review" agents/
   ```

3. **Create the file.** Copy `agents/_template.md` to the appropriate directory:
   ```bash
   cp agents/_template.md agents/01-development/my-new-agent.md
   ```

4. **Fill in the frontmatter.** All required fields must be present and valid.

5. **Write the prompt body.** Follow the template structure: Role, Core Capabilities, Input Format, Output Format, Decision Framework, Example Usage, Constraints.

6. **Validate.** Run the validation script:
   ```bash
   python scripts/validate-agents.py
   ```

7. **Build the index.** Regenerate the agent catalog:
   ```bash
   python scripts/build-agent-index.py
   ```

8. **Test.** Use the agent in a real conversation to verify it works as intended.

### Updating an Existing Agent

1. **Read the current file** to understand the existing prompt.
2. **Make your changes** while preserving the overall structure.
3. **Bump the version** in the frontmatter:
   - Patch (1.0.0 -> 1.0.1): Bug fixes, typo corrections, minor wording improvements
   - Minor (1.0.0 -> 1.1.0): New capabilities, additional constraints, expanded examples
   - Major (1.0.0 -> 2.0.0): Complete rewrite, changed role, incompatible output format
4. **Validate and rebuild index.**

### Market Analysis Prompts (Special Case)

The structured prompts in `src/agents/prompts/market_analysis/` use a different format: YAML files with explicit input/output schemas, instrument assignment, scheduling, and model routing. These are not validated by the agent schema validator but instead by the pipeline runner.

When adding a new market analysis prompt:

1. Use an existing prompt in the same `*.yaml` file as a template
2. Define `input_schema` listing all required data inputs
3. Define `output_schema` with typed fields
4. Set `instrument` to one of the 12 tracked instruments (or `null` for cross-instrument)
5. Set `model` to the appropriate tier (haiku for simple analysis, sonnet for multi-factor)
6. Set `schedule` to `every_run`, `daily`, or `weekly`
7. Write the `prompt` with instrument-specific context and always end with "Output JSON only. Never fabricate data."

### Directory Structure After Adding

After adding agents, the directory should look like:

```
agents/
  _schema.json          # Do not modify unless adding new fields
  _template.md          # Do not modify; copy to create new agents
  01-development/
    coder.md
    reviewer.md
    your-new-agent.md   # <-- your addition
    ...
```

### Commit Message Convention

When committing agent changes:

```
feat(agents): add [agent-name] to [domain]

- [Brief description of what the agent does]
- [Any notable design decisions]
```

For updates:

```
fix(agents): update [agent-name] v1.0.0 -> v1.1.0

- [What changed and why]
```
