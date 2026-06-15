---
name: support-emails-to-features
description: Unified "incoming for me" briefing for Product Manager — fetches both (a) Jira issues newly assigned to you by someone else and (b) email action items from Apple Mail.app. Produces one combined digest with priority sorting. Use when asked about 'what's incoming', 'incoming for me', 'my incoming work', 'inbox + jira', 'what landed on my plate', 'newly assigned', or '/incoming'.
argument-hint: [--since <Nd>] [--no-email] [--no-jira] [--mark-read]
---

# Incoming — Product

One-shot morning briefing: shows everything that landed on the user's plate without their initiation — **new Jiras assigned to them by other people** + **email action items from Mail.app**. Resolves "the user" from `team.json` (the PM running this).

This skill is a thin orchestrator. It delegates email handling to the same scripts used by `/outlook-actions` and Jira fetching to `tools/jira-api.py`. Both halves run in parallel.

## Step 0: Bootstrap

Read silently:

1. `team.json` — to resolve the user's Atlassian accountId. The user is the PM running this (identify their entry in `team.json`); their `atlassianId` is the canonical lookup key. Don't hardcode the ID in this SKILL.md — always re-read from team.json.
2. `.claude/skills/outlook-actions/owned-people.txt` — reused for email classification (anyone-addressed-by-name → Action).
3. Parse `$ARGUMENTS`:
   - `--since <Nd>` — window for both Jira (`created >= -Nd`) and email (`--since` window). Default `7d`.
   - `--no-email` — skip the email half.
   - `--no-jira` — skip the Jira half.
   - `--mark-read` — after the summary, prompt to mark surveyed unread emails as read (delegates to outlook-actions/scripts/mark-read.js).

Resolve repo root with the same pattern as `/outlook-actions`:
```bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

## Step 1: Fetch in Parallel

Run both fetches in parallel using two Bash tool calls in the same message.

### Step 1a: Jira — newly assigned to user, reported by someone else

```bash
USER_ID="$(python3 -c 'import json; print(next(p["atlassianId"] for p in json.load(open("team.json")) if p.get("alias")=="MK"))')"
python3 tools/jira-api.py search "project = ${PROJECT_KEY} AND assignee = \"$USER_ID\" AND reporter != \"$USER_ID\" AND statusCategory != Done AND created >= -${SINCE_DAYS}d ORDER BY created DESC" --max-results 50 --fields summary,assignee,reporter,created,status,priority,labels
```

**If the result is "No issues found" but you suspect that's wrong** (e.g. you know there should be Jiras), run a sanity check:
```bash
curl -s -u "$ATLASSIAN_EMAIL:$ATLASSIAN_API_TOKEN" "https://$ATLASSIAN_SITE/rest/api/3/myself" | head -c 200
```
A 401 / "Client must be authenticated" response means the token is expired — surface this to the user with: "Your Atlassian API token has expired or is invalid. Refresh it at https://id.atlassian.com/manage-profile/security/api-tokens and update `ATLASSIAN_API_TOKEN` in `.env`." Then continue with the email half only.

### Step 1b: Email — Mail.app unread inbox

```bash
osascript -l JavaScript "$REPO_ROOT/.claude/skills/outlook-actions/scripts/fetch-mail.js" "${SINCE_HOURS:-168}"
```

(168 hours = 7 days; convert from `--since`.)

Apply the same noise filter and classification logic as `/outlook-actions` Steps 2–5. Don't duplicate the rules — reference the SKILL.md if uncertain. Use `owned-people.txt` for the Product Manager/Khushali address-match override.

## Step 2: Render the Combined Digest

Print this to terminal (markdown):

```markdown
# 📥 Incoming for Product Manager — last <window>

## 🎫 New Jiras assigned to you (<N>)

| Key | Pri | Reporter | Created | Status | Summary |
|-----|-----|----------|---------|--------|---------|
| ${PROJECT_KEY}-XXXXX | High | Project Coordinator | May 12 | To Do | Add referral source filter to dashboard |
| ${PROJECT_KEY}-YYYYY | Med  | Jane Doe | May 11 | To Do | Spec subscription pause flow for v3.4 |
...

> If 0: "No new Jiras assigned to you in the last <window> — clean slate."

## 📧 Email action items (<M>)

| Pri | Sender | Subject | Received | Suggested action |
|-----|--------|---------|----------|------------------|
| P0  | Project Coordinator | Q2 sign-off needed | May 13, 02:27 IST | Reply with Meta-budget decision |
...

> If 0: "Inbox is clear — no email action items in the last <window>."

## ℹ️ Email FYI (<K>)

| Sender | Subject | Received |
|--------|---------|----------|
| ... | ... | ... |
```

Sort within each section:
- Jiras: by `priority` descending (Highest → Lowest), then `created` descending.
- Emails: by `P0 → P1 → P2`, then `time_received` descending within priority.

## Step 3: Optional Mark-Read (only if `--mark-read`)

Skip if `--mark-read` was NOT passed.

Otherwise: prompt via `AskUserQuestion` to mark surveyed unread emails as read, same flow as `/outlook-actions` Step 7.5. Reuse `.claude/skills/outlook-actions/scripts/mark-read.js`.

For Jiras: **never auto-acknowledge or transition** — those are intent-bearing actions that need the user's explicit instruction. Only show them; don't touch.

## Step 4: Final Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Incoming — last <window>
Jiras assigned by others: <N> (highest: ${PROJECT_KEY}-XXXXX, <summary>)
Email actions: <M> (top: <subject>)
Email FYI: <K> • Filtered noise: <D>
Marked read: <R> emails
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then offer ONE follow-up only if relevant:
- If high-priority Jira exists: "Want to /analyze-jira <KEY> to plan it?"
- If high-priority email needs Jira: "Want me to convert action item #1 to a Jira via /jira?"
- Otherwise: silence is fine. Don't bombard with options.

## What this skill does NOT do

- Does NOT include Jiras the user reported themselves (those aren't "incoming" — they're outgoing)
- Does NOT include Jiras already Done (`statusCategory != Done` filter)
- Does NOT include emails not in the unread + recent window
- Does NOT auto-create Jiras from emails — that's `/outlook-actions` per-row walk
- Does NOT push notifications, post to Slack, or alert anyone else
- Does NOT modify Jira state (no transitions, comments, or edits)
- Does NOT replace `/plan-my-day` — that's broader (PRs, meetings, dependencies). `/incoming` is the narrow "what arrived for me" subset

## Edge Cases

- **Atlassian token expired** — surface clearly, continue with email-only output. Don't silently show zero Jiras.
- **No unread email + no new Jiras** — say so cheerfully ("Empty queue — go do focused work.") and exit.
- **Many Jiras (>20)** — show top 10 with a "+ N more" line. Most days have <10; if it's >20, something's wrong upstream and worth surfacing.
- **Mail.app permission not granted** — same error handling as `/outlook-actions` (point to System Settings → Privacy & Security → Automation).
- **User invokes `--since 30d`** — that's a "catch-up after vacation" pattern, fine. Cap at 90d.
