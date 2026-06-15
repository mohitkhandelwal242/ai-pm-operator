---
name: operator-help
description: "Discovery guide for the AI-PM Operator — answers 'what can you do for me?'. Lists every installed skill grouped by PM job-to-be-done and recommends a tailored starter set based on the user's business.json (business type, platforms, revenue model). Use when the user says '/help', 'help', 'what can you do', 'which skill', 'what skills do I have', 'list skills', 'getting started', 'where do I start', or seems unsure what to run."
argument-hint: "[topic]"
allowed-tools: [Read, Bash]
---

# AI-PM Operator — Help & Discovery

Your job: be the menu. The user has ~15 skills and needs to know what's available and **what to run for their business**. Keep this skimmable — this is a guide, not a report. No network calls. No license logic (a hook handles that).

If `$ARGUMENTS` names a topic (e.g. "analytics", "competitors", "planning"), focus the answer on the matching group but still end with tailored next commands.

---

## Step 1 — Load context

```bash
ls business.json 2>/dev/null
ls .claude/skills/
```

- If `business.json` is **missing** → tell the user: "Looks like the Operator isn't set up yet. Run `/operator-onboarding` first so I can tailor recommendations to your business." Then show the grouped skill menu (Step 2) anyway, but skip the tailored recommendations.
- If present → `Read business.json` for `company.business_type`, `company.primary_platforms`, `company.revenue_model`, `metrics.key_metrics`, `competitors`, and `stack`. Only list skills that actually exist in `.claude/skills/`.

---

## Step 2 — The menu (group by job-to-be-done)

Present the installed skills grouped like this. Include only skills that exist on disk; drop any that don't.

**🌅 Daily / standup**
- `/scrum-master` — audit board flow, find blockers & stale tickets, keep Jira clean
- `/support-to-features` (`support-emails-to-features`) — "incoming for me": newly assigned Jira + email action items in one digest

**🗺️ Plan & prioritize**
- `/weekly-plan` — weekly capacity review, carry-overs, next-week priorities per person
- `/idea-generator` — brainstorm new opportunities (and create/improve skills)

**📐 Specs & delivery**
- `/prd-generator` — turn a raw idea into a full Given/When/Then PRD
- `/jira-vs-code` (`jira-vs-code-mismatch`) — catch spec-vs-code drift before you commit
- `/release-notes` (`release-notes-writer`) — leadership/product-weekly slide content from ships

**📊 Analytics & reporting**
- `/weekly-metrics` (`weekly-metrics-analyst`) — GA4 weekly traffic & anomaly report
- `/board-prep` (`monthly-board-prep`) — month-over-month leadership/board outline
- `/ppa` (`product-performance-analysis`) — post-launch flow metrics & adoption vs targets
- `/play-console` (`play-console-insights`) — Play Store ASO, CVR, search terms, vitals
- `/search-console` (`search-console-insights`) — Google Search Console keyword & CTR wins

**🛰️ Market & customers**
- `/competitor-tracker` (`deep-competitor-tracker`) — weekly competitor audit & discovery
- `/support-to-features` — cluster customer/support signals into epics (also a daily skill)

**💰 Offers & monetization**
- `/audit-offers` (`jira-scoring-rice`) — free-offer / discount inventory & ROI audit, kill/keep/consolidate

**🧭 Meta / setup**
- `/operator-onboarding` — first-run setup & `--reconfigure`
- `/operator-help` — this guide

> If the dir listing shows a skill not in the groups above, add it under the closest-matching group rather than dropping it. If a grouped skill is **absent** from disk, omit that line.

---

## Step 3 — Tailored starter set (from business.json)

Pick the most relevant skills for **this** business and explain the "why" in one line each. Use these heuristics:

- **business_type = Consumer mobile/web app** → `/play-console` (if android/ios), `/support-to-features`, `/scrum-master`, `/weekly-metrics`
- **business_type = B2B SaaS** → `/scrum-master`, `/weekly-plan`, `/weekly-metrics`, `/board-prep`, `/prd-generator`
- **business_type = Marketplace / platform** → `/board-prep`, `/ppa`, `/competitor-tracker`, `/weekly-metrics`
- **business_type = E-commerce / D2C** → `/weekly-metrics`, `/search-console`, `/competitor-tracker`, `/audit-offers`
- **revenue_model = Subscription** → highlight `/audit-offers` and `/board-prep` (offer ROI + churn/MRR)
- **revenue_model = Ads / has a web domain** → highlight `/weekly-metrics` + `/search-console`
- **competitors present** → highlight `/competitor-tracker`

**Mark not-applicable, don't hide:**
- No `android`/`ios` in `primary_platforms` → `/play-console` = **N/A (no mobile app)**
- No `website_domain` → `/search-console` and `/weekly-metrics` = **optional (no website connected)**
- `stack.docs` not Confluence → note that report-publishing skills will output locally instead

Render as a short list, e.g.:

> **Recommended for {product_name} ({business_type}, {revenue_model}):**
> 1. `/scrum-master` — keep your {PROJECT_KEY} board healthy daily
> 2. `/play-console` — you're on {platforms}, so ASO & ratings matter
> 3. `/board-prep` — monthly story for your {key_metric} goal
> _N/A for you: …_

---

## Step 4 — Three concrete next commands

Close with exactly **3** tailored commands the user can paste right now, drawn from the starter set, each with a tiny reason. Examples (substitute their real values):

- "`/scrum-master` — sweep your board for blockers"
- "`/prd-generator` — draft a spec for your next feature"
- "`/competitor-tracker` — first pulse on {their competitors}"

Then one line: "Want detail on any group? Run `/operator-help <topic>` (e.g. `/operator-help analytics`)."

---

## Principles
- **Menu, not report.** Skimmable. Group, recommend, point to 3 next steps — then stop.
- **Only real skills.** List exactly what's in `.claude/skills/`; never invent a skill.
- **Business-aware.** Tailor from `business.json`; mark irrelevant tools N/A with the reason.
- **No side effects.** Read-only. No network, no license checks, no file writes.
