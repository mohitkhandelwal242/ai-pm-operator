---
name: operator-onboarding
description: "First-run setup for AI-PM Operator. Detects a fresh install, infers the user's business from the surrounding repo, asks a short set of questions, then writes business.json / .env / team.json and tailors every skill to the user's business. Use on first launch, when config is missing, or when the user says 'set up', 'onboard', 'configure', 'get started', or '/onboard'."
argument-hint: "[--reconfigure]"
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion]
---

# AI-PM Operator — Onboarding

Your job: take someone who just pulled this repo and get them from zero to a working, **business-tailored** AI-PM Operator in one short conversation. They could be a PM at any kind of company (B2B SaaS, consumer app, marketplace, e-commerce, fintech, dev tools…). Nothing here is specific to any one business — you learn theirs and configure accordingly.

**Run this when:** `business.json` is missing, `.env` is missing, the user asks to "set up / onboard / configure", or `--reconfigure` is passed.

---

## Step 0 — Detect state

```bash
ls -la .env business.json team.json 2>/dev/null
```
- If `.env` and `business.json` both exist and `--reconfigure` was NOT passed → tell the user they're already set up, show `/operator-onboarding --reconfigure` to redo, and stop.
- Otherwise continue.

Copy templates if the working files don't exist yet:
```bash
[ -f business.json ] || cp business.json.template business.json 2>/dev/null
[ -f .env ] || cp .env.example .env 2>/dev/null
```

---

## Step 1 — Infer the business from the repo (do this BEFORE asking)

Scan the surrounding working directory so your questions are smart, not generic. Don't dump raw output — infer.
- Tech stack & platforms: look for `package.json`, `requirements.txt`, `go.mod`, `build.gradle`/`AndroidManifest.xml`, `Podfile`/`*.xcodeproj`, `composer.json`, `Dockerfile`.
- Product signals: read `README.md`, `package.json` (name/description), landing copy, `/docs`, app store config — infer product name, what it does, who it's for.
- Repo/Jira hints: `git remote -v`, existing branches, any Jira keys in commit messages (`git log --oneline -30`).

Form a **draft hypothesis**: "Looks like you're building **{product}**, a **{business_type}** in **{industry}** for **{target_users}**, on **{platforms}**." You'll confirm this with the user rather than asking from scratch.

---

## Step 1b — Show value FIRST (read-only, no credentials needed)

Before asking for any credentials, prove the Operator is worth configuring. Produce ONE quick, impressive, read-only artifact using only what's already on hand — nothing that needs Jira/Confluence/API keys:
- If there's a backlog/spec/notes file or the user can paste a few raw feature ideas → run a mini `/prioritize` (RICE/ICE on what they paste) **or** draft a quick PRD outline for one idea.
- Or, from the repo + your business hypothesis, produce a 5-bullet "first-week PM plan" tailored to their business.
- Or, if they name 2-3 competitors, give a quick positioning read.

Keep it under a minute and end with: "That's a taste — connect your tools next and I can do this against your real Jira / analytics / customers." This is the activation moment; don't skip it.

---

## Step 2 — Confirm the business profile (ask, pre-filled with your inference)

Use `AskUserQuestion` for the structured choices, plain prompts for free text. Pre-fill everything you inferred — the user should mostly be confirming.

Collect (write into `business.json`):
- **company.name**, **company.product_name**, **company.one_liner**
- **company.business_type** — offer: `B2B SaaS`, `Consumer mobile/web app`, `Marketplace / platform`, `E-commerce / D2C` (plus Other)
- **company.industry** (free text, e.g. fintech, health, dev tools)
- **company.revenue_model** — `Subscription`, `Transaction/commission`, `Ads`, `One-time/licenses` (plus Other)
- **company.target_users** (free text)
- **company.primary_platforms** — multi-select: `web`, `ios`, `android`, `api/backend`
- **company.website_domain**
- **metrics.north_star** + **metrics.key_metrics** — suggest sensible defaults per business_type (e.g. SaaS → MRR, activation, churn; marketplace → GMV, liquidity, take rate; consumer app → DAU/MAU, retention, installs) and let them edit.
- **competitors** — ask for 2-5: name, website domain, and (if they have a mobile app) Android package / iOS id. If they don't know, leave `competitors: []` — competitor skills will prompt later.
- **stack** — confirm issue tracker (default Jira), docs (default Confluence, optional), analytics (GA4 optional), and list their main code repos if relevant.
- **context_notes** — one free-text field for anything else that helps (positioning, current focus, constraints).

Write `business.json` with the confirmed values (valid JSON, drop the `_comment`).

---

## Step 3 — Connect tools (credentials → .env)

Walk through credentials, skipping anything they don't use. For each, explain what it unlocks, let them skip, AND tell them exactly **where to find it** (this is the #1 place people get stuck — don't make them go hunting):
- **Jira** (most skills): `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_PROJECT_KEY`.
  - *Where:* URL = `https://<your-company>.atlassian.net`. Token = create one at **https://id.atlassian.com/manage-profile/security/api-tokens** ("Create API token"). Project key = the prefix on your issue IDs (e.g. `PROJ` in `PROJ-123`), visible in any Jira ticket or Project settings → Details.
  - Validate by fetching the project; on success show the project name.
- **Confluence** (publishing reports, optional): `CONFLUENCE_SPACE_KEY`, `CONFLUENCE_PARENT_PAGE_ID`, `CONFLUENCE_CLOUD_ID`.
  - *Where:* Space key = the short code in a Confluence URL `/wiki/spaces/<KEY>/...`. Parent page id = open the page you want reports filed under; the number in its URL `/pages/<ID>/...`. Cloud id = visit `https://<your-company>.atlassian.net/_edge/tenant_info` (it returns your `cloudId`).
- **Analytics** (optional): `GA4_PROPERTY_ID` + `GOOGLE_APPLICATION_CREDENTIALS`, `GSC_PROPERTY_URL`.
  - *Where:* GA4 property id = GA4 → Admin → Property settings (a 9-digit number). GSC url = the property as shown in Search Console (e.g. `https://acme.com`). Service-account JSON: GA4 → Admin → grant the service account "Viewer".
- **Project domain**: set `PROJECT_DOMAIN` = `company.website_domain`, `PROJECT_KEY` = the Jira project key.

Prefer running `python3 tools/setup-wizard.py` for the credential + validation flow if the user wants a guided script; otherwise write `.env` directly. Either way, confirm `.env`, `business.json`, and `team.json` are in `.gitignore`.

---

## Step 4 — Team roster (team.json)

Ask for the key people they work with (name, alias, email, role, domains). 2-4 is plenty to start. **Don't make them hunt for Atlassian account IDs** — if Jira is configured, auto-resolve each person's `atlassianId` for them from their name/email:
```bash
python3 tools/jira-api.py lookup "jane@company.com"   # returns the accountId
```
Fill `atlassianId` from the lookup; only ask manually if the lookup finds nothing. Write `team.json`. If they want to skip, write an empty roster `[]` and note they can add people later.

---

## Step 5 — Tailor the skills to their business

This is what makes it *theirs*. Using `business.json`:
- **Competitor tracking**: write `.claude/knowledge/competitor-audit/competitors.md` + `scan-urls.json` from their `competitors` list and `business_type` (derive discovery search queries from their industry/space — NOT any fixed vertical). If no competitors given, leave a template and tell them `/competitor-tracker` will help add some.
- **Metrics skills** (monthly analysis, performance, weekly metrics): note their `metrics.key_metrics` and `revenue_model` so reports speak their language.
- **Platform-specific skills**: if they have no mobile app, mark `play-console-insights` as not-applicable; if no website, mark SEO/analytics skills optional.

Don't rewrite the skill files — they read `business.json` at runtime. Just generate the per-business data files above.

---

## Step 5b — Register the install (disclosed analytics)

Tell the user plainly: "AI-PM Operator sends the maker a **non-sensitive business summary** (company/product name, business type, industry, platforms) so they can see what kinds of businesses use it — **never your credentials or team data**. You can opt out by setting `OPERATOR_TELEMETRY=off` in `.env`." Then register the install:
```bash
python3 tools/telemetry.py install
```
If they opted out, skip the call. Do not treat this as optional/hidden — it must be disclosed.

---

## Step 6 — Readiness summary

Show a concise table: each skill → ✅ ready / ⚠️ needs {credential} / — not applicable to your business. End with 2-3 concrete first commands tailored to them, e.g.:
- "`/scrum-master` — audit your {PROJECT_KEY} board"
- "`/prd-generator` — draft a spec for your next feature"
- "`/competitor-tracker` — first pulse on {their competitors}"

Confirm: "You're set up. Re-run `/operator-onboarding --reconfigure` any time your business or tools change."

---

## Principles
- **Infer first, ask second.** Respect their time — confirm hypotheses, don't interrogate.
- **Everything optional degrades gracefully.** Skipped credentials just mark those skills inactive; the rest work.
- **No vertical assumptions.** Never hardcode an industry, competitor, or metric set — always derive from `business.json`.
- **Local only.** All config stays on their machine and gitignored.
