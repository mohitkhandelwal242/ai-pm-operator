# Skill Templates

Two archetypes. Pick the one that fits, then customize.

---

## Template A: Expert/Advisor

Use when the skill loads domain knowledge and answers questions across a session.
Examples: `/backend-nodejs`, `/mob-ios`, `/mob-android`, `/devops-aws-ecs`

```markdown
---
name: {kebab-case-name}
description: "{Domain} domain expert for Product — loads {what knowledge}. Use for {capabilities}. NOT a task executor — use /{task-skill} for that."
---

# {Title} — Product

You are a **senior {domain} expert** for Product. You are domain-loaded and ready for
ongoing assistance: {list capabilities like architecture Q&A, code review, debugging}.

You are NOT executing a specific task — for that, use `/{task-executor-skill}`.

## Step 0: Load Domain Knowledge

Before responding, load silently (don't announce each read):
1. `team.json` — team roster
2. `.claude/knowledge/{relevant-guidelines}.md`
3. Scan `.claude/knowledge/product-modules/` — list available modules

Load on demand when the user asks about a specific area:
- `.claude/knowledge/product-modules/{module}/overview.md`
- `.claude/knowledge/database/product-mysql-schema.csv` — for DB questions

## Step 1: Introduce Yourself

> **{Expert Name} loaded.**
> I've loaded {what}. Module deep-dives load on demand.
> Ask me anything: {topic list}.

## Expert Responsibilities

### {Category 1}
- {specific guidance}
- {specific guidance}

### {Category 2}
- {specific guidance}

### When to Defer
- For implementation tasks → suggest `/{task-skill}`
- For cross-cutting concerns → suggest the relevant specialist skill
```

---

## Template B: Task Executor

Use when the skill runs a workflow and produces a concrete output.
Examples: `/scrum-master`, `/qa-test-cases`, `/retro`, `/audit-meta`

```markdown
---
name: {kebab-case-name}
description: "{Verb} {what} — {key details}. Use when {trigger-phrase-1}, {trigger-phrase-2}, or '/{name}'."
argument-hint: <required-arg> [--optional-flag]
---

# {Title} — Product

{One sentence: what this workflow does and why it matters.}

## Step 0: Bootstrap

Read silently:
1. `team.json` — roster, domains, aliases
2. `.claude/knowledge/{relevant-file}.md` — domain context
3. Parse `$ARGUMENTS`

Constants:
- JIRA_CLI: `python3 tools/jira-api.py`

## Step 1: {Gather Data}

Run independent queries in parallel:

{Show the actual commands — Jira searches, DB queries, file reads, API calls.}

## Step 2: {Analyze}

{Core logic — the thing that makes this skill valuable.
Decision tables, categorization rules, metric calculations, etc.}

## Step 3: {Generate Output}

{Create the deliverable. Be specific about format:
- Markdown table for terminal output
- HTML for Confluence
- Test files for code output}

## Step 4: {Deliver}

Route output to the right destination:

- **Report** → publish to Confluence via Atlassian MCP
  - Parent page: {space/section}
  - Format: HTML storage format
  - Include: date, data sources, author
- **Action items** → create Jira issues via `/create-jira`
  - Auto-assign based on team.json domains
  - Add labels: {relevant labels}
- **Code/tests** → write to repo
  - Path: {where in the repo}

## Final: Report to User

Concise summary (under 50 lines):
- What was done
- Links to outputs (Confluence page, Jira issues, files)
- Suggested next steps
```

---

## Frontmatter Field Reference

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | kebab-case, matches directory name |
| `description` | Yes | Under 200 chars. Include trigger phrases. Be "pushy" — list what should invoke it |
| `argument-hint` | No | Show expected input format: `<required> [--optional]` |
| `allowed-tools` | No | Only set if restricting. Omit to allow all tools |

## Subskill Pattern

If the skill has a variant (different cadence, trigger, or scope), add a separate `.md` file:

```
my-skill/
├── SKILL.md          — main workflow
└── daily-ops.md      — subskill for daily automation
```

Document it at the top of SKILL.md:

```markdown
## Subskills

This skill has a **daily-ops** subskill:
- **Trigger**: "run daily ops", "daily {domain}"
- **Instructions**: See `daily-ops.md` in this directory
- **What it does**: {1-2 lines}

When the user asks to run daily ops, load `daily-ops.md` instead.
```
