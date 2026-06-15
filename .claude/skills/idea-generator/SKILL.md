---
name: idea-generator
description: "Create new AI-PM Operator skills, improve existing ones, and ensure they follow Product conventions. Use when anyone says 'create a skill', 'make a skill', 'new skill for X', 'turn this into a skill', 'improve /skill-name', or '/skill-creator'. Also use when a workflow gets repeated enough that it should be captured as a reusable skill. Proactively suggest this skill when you notice the user doing the same multi-step workflow for the third time."
argument-hint: "[skill-name] [--improve] [--from-conversation]"
---

# Skill Creator — AI-PM Operator

Create new skills or improve existing ones. Every skill you create joins a toolkit used daily by the Product engineering team — it must be practical, well-integrated, and follow AI-PM Operator conventions.

## Step 0: Bootstrap

Read silently (don't announce):
1. `team.json` — team roster, domains, aliases
2. `CLAUDE.md` — non-negotiable rules, key references
3. List `.claude/skills/` — know what already exists (avoid duplicates/overlaps)

Parse `$ARGUMENTS`:
- If a skill name is given → check if it exists under `.claude/skills/{name}/`
- If `--improve` → load existing SKILL.md, enter improvement mode (Step 4)
- If `--from-conversation` → extract the workflow from conversation history
- If no args → interactive creation mode (Step 1)

---

## Step 1: Capture Intent

Understand what the skill should do before writing anything. If the conversation already contains a workflow the user wants to capture (e.g., "turn this into a skill"), extract answers from context first — tools used, steps taken, corrections made, input/output formats observed.

Ask the user to confirm or fill gaps on these questions:

1. **What does this skill do?** (one sentence)
2. **Archetype**: Is it an **Expert/Advisor** (loads knowledge, answers questions) or a **Task Executor** (runs a workflow, produces output)?
3. **When should it trigger?** (what would someone type to invoke it?)
4. **What inputs does it need?** (Jira key? PR number? free text? flags?)
5. **What does it output?** Where should outputs go?
   - **Report/analysis** → Confluence (use Atlassian MCP to publish)
   - **Action items** → Jira (use `/create-jira` to create issues)
   - **Code/tests** → files in the repo
   - **Summary** → terminal output
6. **Which integrations does it need?**
   - Product MySQL DB → `mcp__product-mysql__mysql_query`
   - Jira → `tools/jira-api.py` (never Atlassian MCP for Jira)
   - Confluence → Atlassian MCP (`searchConfluenceUsingCql`, `createConfluencePage`)
   - Code search → `mcp__codebase-memory-mcp__*`
   - WhatsApp → `/whatsapp-send`
   - Web search → `WebSearch` / `WebFetch`
   - AWS/DevOps → `Bash` with `aws` CLI
7. **Who is the audience?** (dev team, CTO, QA, external?)

---

## Step 2: Check for Overlaps

Before writing, check whether an existing skill already covers this ground:

```
Existing skills to check against:
├── Expert/Advisor: backend-nodejs, mob-ios, mob-android, devops-aws-ecs
├── Task Executor: backend, ios, android, scrum-master, qa-test-cases
├── Analysis/Audit: audit-meta, audit-api, audit-screen, competitor-audit, flow-metrics
├── QA Pipeline: qa-check, qa-fill, qa-delta, qa-seed, qa-gaps, qa-verify
├── Reporting: retro, funnel, install-funnel, analytics-subscription-trend
├── Jira Workflow: create-jira, analyze-jira, implement-jira, focus-review
├── Communication: whatsapp-send, whatsapp-create, whatsapp-templates, freshdesk
├── Code Quality: code-review, backend-tests, backend-e2e-tests, playwright-tests
└── Rituals: plan-my-day, good-morning, good-night, self-improve
```

If overlap exists, present options:
- **Extend** the existing skill (add a subskill like `daily-ops.md`)
- **Split** — carve out the new concern into its own skill with clear boundaries
- **Replace** — if the existing skill is outdated or poorly structured

Get confirmation before proceeding.

---

## Step 3: Write the SKILL.md

### 3a) Frontmatter

```yaml
---
name: {kebab-case-name}
description: "{what-it-does} — {key-details}. Use when {trigger-phrases}, or '/{name}'."
argument-hint: {arg-format}  # optional
allowed-tools: [...]          # optional, only if restricting
---
```

**Description rules:**
- One line, under 200 characters ideally
- Include what it does AND when to trigger it
- Be slightly "pushy" — list trigger phrases so Claude invokes it reliably
- Clarify what NOT to use it for if there's a sibling skill (e.g., `/backend-nodejs` vs `/backend`)

### 3b) Body Structure

Follow the appropriate template from `references/skill-template.md` in this directory. Read it now and use the matching archetype (Expert/Advisor or Task Executor).

### 3c) Product Conventions Checklist

Before finalizing, verify the skill follows these:

| Convention | Check |
|-----------|-------|
| **Jira** | Uses `tools/jira-api.py`, never Atlassian MCP for Jira |
| **Confluence** | Uses Atlassian MCP for publishing reports |
| **DB queries** | Uses `mcp__product-mysql__mysql_query`, never raw SSH |
| **Code search** | Uses codebase-memory-mcp first, Grep/Glob as fallback |
| **team.json** | Loaded in Step 0 for people references |
| **No hardcoded paths** | Uses relative paths only (shared repo) |
| **Parallel fetches** | Independent queries run in parallel |
| **Graceful fallback** | Works even if optional dependencies are missing |
| **Output location** | Reports → Confluence, actions → Jira, code → repo files |
| **Confirmation before side effects** | Ask before Jira comments, emails, publishes |
| **Date handling** | Always use absolute dates, filter web searches to 2025-2026 |
| **Kanban, not Scrum** | No "sprint" language — use flow-based terms |

---

## Step 4: Improve an Existing Skill

When `--improve` is passed or the user asks to improve a skill:

1. **Read the current SKILL.md** — understand what it does today
2. **Check recent usage** — ask the user what works and what doesn't
3. **Audit against conventions** — run the checklist from Step 3c
4. **Identify gaps:**
   - Missing integrations (should it publish to Confluence? Create Jira issues?)
   - Poor description (not triggering when it should?)
   - Missing Step 0 bootstrap (not loading team.json or knowledge files?)
   - Hardcoded paths or values
   - Missing subskills (would a daily-ops variant be useful?)
5. **Propose changes** — show before/after for the description, list structural changes
6. **Apply with confirmation**

---

## Step 5: Test the Skill

After writing the skill, verify it works:

1. **Dry run** — mentally walk through the skill with a realistic input. Does each step have what it needs from the previous step?
2. **Tool availability** — verify every tool referenced is actually available (check ToolSearch if unsure)
3. **File paths** — verify every knowledge file referenced actually exists
4. **Edge cases** — what happens with no arguments? Invalid Jira key? Empty results?

Propose 2-3 test prompts to the user:
```
"Here are test cases I'd try:
1. /{skill-name} ${PROJECT_KEY}-12345
2. /{skill-name} --flag
3. /{skill-name}  (no args — should it prompt or error?)

Want me to run any of these?"
```

---

## Step 6: Subskills (Optional)

If the skill has a variant that runs on a different cadence or trigger (like scrum-master's `daily-ops.md`):

1. Create a separate `.md` file in the skill directory
2. Document it in the main SKILL.md under a `## Subskills` section at the top
3. Include trigger phrases so Claude knows when to load the subskill instead

```markdown
## Subskills

This skill has a **{subskill-name}** subskill:
- **Trigger**: "{phrase1}", "{phrase2}", or any {context}
- **Instructions**: See `{subskill-name}.md` in this directory
- **What it does**: {1-2 line summary}

When the user asks to {trigger}, load and follow `{subskill-name}.md` instead.
```

---

## Step 7: Finalize

After the skill is written and the user approves:

1. **Verify the skill appears** — the skill should show up when typing `/` in Claude Code
2. **Update CLAUDE.md** if needed — only if the skill introduces a new non-negotiable rule
3. **Propose self-improvement** — if creating this skill revealed a gap in AI-PM Operator's conventions or knowledge:
   ```
   Improvement candidate:
     Finding: {what was learned}
     Scope:   General — applies to all  OR  Specific to {X} only
     Target:  {proposed file}
     Reason:  {why}
   → Encode as proposed? (yes / no + correction)
   ```

---

## Reference: Output Routing Guide

Where should skill outputs go? Use this decision tree:

```
Is the output a report/analysis meant for stakeholders?
  YES → Publish to Confluence
        - Use Atlassian MCP: createConfluencePage
        - Format: HTML (Confluence storage format)
        - Always include: date, author, data sources

Is the output an action item or task?
  YES → Create in Jira
        - Use: /create-jira (delegates to tools/jira-api.py)
        - Auto-assign based on team.json domains
        - Add appropriate labels and priority

Is the output code, tests, or config?
  YES → Write to repo files
        - Tests: appropriate test directory
        - Specs: specs/{ISSUE-KEY}/
        - Knowledge: .claude/knowledge/

Is the output a notification or alert?
  YES → Consider the audience:
        - Team → Jira comment on relevant issue
        - Individual → mention in Jira or suggest WhatsApp
        - CTO → terminal summary + Confluence for reference

Is the output a one-time answer?
  YES → Terminal output only
        - Concise summary table
        - Under 50 lines
```

---

## Reference: Integration Cheat Sheet

```yaml
Jira (read/write):
  tool: python3 tools/jira-api.py
  commands: search, comment, create, edit, get
  note: NEVER use Atlassian MCP for Jira

Confluence (read/write):
  tool: Atlassian MCP
  read: mcp__claude_ai_Atlassian__searchConfluenceUsingCql
  write: mcp__claude_ai_Atlassian__createConfluencePage
  note: Load via ToolSearch first

MySQL (read-only):
  tool: mcp__product-mysql__mysql_query
  note: Auto-adds LIMIT 100, read-only user

Code search:
  tool: mcp__codebase-memory-mcp__search_graph / search_code
  fallback: Grep, Glob, Read
  note: Always try codebase-memory-mcp FIRST

Web research:
  tool: WebSearch + WebFetch
  note: Always filter to 2025-2026

WhatsApp:
  tool: /whatsapp-send skill
  note: For user notifications via WhatsApp

Team data:
  file: team.json
  note: Load in Step 0, use for assignment/routing
```
