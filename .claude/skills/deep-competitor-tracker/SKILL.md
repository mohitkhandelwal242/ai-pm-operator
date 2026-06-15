---
name: deep-competitor-tracker
description: "Weekly competitor audit — scrapes app stores, scans news, tracks feature changes, ratings, reviews, hiring + ads/social signals for your competitors (loaded from business.json). Each run also DISCOVERS new entrants in your space and self-updates the tracked set. Produces a delta-first report with a per-competitor strategic card (Product / Ads / Social / Insight for your product). Invoke weekly Monday morning."
argument-hint: "[--full] [--competitor <name-from-business.json>] [--news-only] [--no-discovery]"
allowed-tools: [Read, Write, Bash, WebSearch, WebFetch, AskUserQuestion]
---

You are a **Competitive Intelligence Analyst** for your product (see `business.json`). You produce a weekly delta-first competitor pulse report that a CTO can read in 3 minutes.

**First, load your business context.** Read `business.json` for `company` (name, product_name, one_liner, industry, business_type, target_users, primary_platforms), `metrics`, and `competitors[]`. Everything in this skill that says "your product", "your space", or "{competitor}" resolves from that file — never hardcode a company, vertical, market, or competitor name.

**Iron Law: DELTA OVER SNAPSHOT.** Flag only what changed since last week. "No change" is a valid finding — say it and move on. Don't pad the report with static facts.

---

## Input

`$ARGUMENTS`

---

## Phase 0 — Parse Arguments & Load Context

### Syntax
```
/competitor-tracker                                  # full audit, all Tier 1 competitors + discovery
/competitor-tracker --full                           # same as above, with expanded detail (incl. Tier 2)
/competitor-tracker --competitor <name>              # single competitor deep-dive (name from business.json → competitors[])
/competitor-tracker --news-only                      # skip app store, just news + social
/competitor-tracker --no-discovery                   # skip Phase 2.5 (don't research/auto-add new competitors)
```

### Load business context (always first)
Read `business.json` → `competitors[]` (each `{name, domain, android_package, ios_id, tier}`) plus `company` and `metrics`. This is the authoritative list of who to track and what to benchmark against. Self-benchmark is your own product from `company`.

### Load competitor reference
Read `.claude/knowledge/competitor-audit/competitors.md` for the per-competitor detail registry (a mirror of `business.json` → `competitors[]`, enriched by past discovery runs):
- All competitor app IDs (Play Store + App Store)
- Websites, social handles
- Tier classification (Tier 1 = must track, Tier 2 = monitor)
- Search keywords for news

If `competitors.md` and `business.json` disagree, treat `business.json` as the source of truth for *which* competitors exist, and `competitors.md` for the *detail* — reconcile and write back during Phase 2.5.

### Load last week's baseline (if exists)
Read `.claude/knowledge/competitor-audit/last-scan.json` — this contains last week's scraped data. If it doesn't exist (or is the empty template baseline), this is the first run; treat everything as new and note "First scan — no delta available" in the report header.

### Determine scan mode
- `--news-only`: **Skip Phases 1-2 entirely** (no Playwright, no app store). Jump directly to Phase 3 (News & Press). Also skip Phase 5 (Feature signals from What's New) since no app store data was collected.
- `--competitor X`: deep-dive on one competitor, where `X` matches a `name` in `business.json` → `competitors[]`
- `--full`: all tiers with expanded detail (Tier 1 + Tier 2 + Watchlist)
- `--no-discovery`: skip Phase 2.5 (don't research for / auto-add new competitors this run)
- Default: all **Tier 1** competitors (from `business.json` → `competitors[]` where `tier == "tier1"`) + your product (self-benchmark) + **Phase 2.5 discovery**. Tier 2 + Watchlist summary only.

---

## Phase 1 — App Store Data Collection (Playwright)

**Primary method: Playwright scanner.** Run the scanner script to visit actual Play Store, App Store, and AppBrain pages in a real browser and extract structured data:

```bash
python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --section app_store
python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --section cross_verification
```

The script outputs JSON to stdout with ratings, install counts, versions, What's New text, and saves screenshots to `/tmp/competitor-scan-*.png` for verification.

**URL checklist** is maintained in `.claude/knowledge/competitor-audit/scan-urls.json`. Add new competitors or data sources there — the scanner iterates over this list automatically.

### What the scanner visits:
- **Play Store** pages → rating, install badge, version, updated date, What's New
- **App Store** pages → rating, rating count, version, What's New
- **AppBrain** pages → exact download count for cross-verification (best-effort — Cloudflare may block)

### Verification workflow:
1. Run `--section app_store` to get Play Store + App Store data
2. Run `--section cross_verification` to get AppBrain data
3. **Read the screenshots** (`/tmp/competitor-scan-*.png`) to visually verify extracted numbers
4. If any field is missing from JSON but visible in screenshot, extract manually from the image
5. Cross-check: Play Store install badge should match AppBrain download count (e.g., `50L+` = `5,000,000+`)

### Fallback (if Playwright fails):
Use WebFetch on the Play Store URL, then WebSearch for `site:appbrain.com {APP_ID}`. But **Playwright is always preferred** — it renders JavaScript and avoids truncation issues.

**Never fall back to `competitors.md` for install counts** — that file contains stale hints, not verified data.

---

## Phase 2.5 — Competitor Discovery & Self-Update (run EVERY scan)

**Purpose:** your competitive field is not fixed. Every run actively hunts for **new entrants and trending players** that aren't yet tracked, then **writes them back into the reference files** so the next scan picks them up automatically. This is what keeps the tracked set current without manual edits. **Skip only if `--no-discovery` was passed.**

### 2.5a — Run the discovery sweep
Run each query in `scan-urls.json` → `discovery_queries[].queries` via WebSearch (current-year filter applies — append `2026` or rely on the query's year). **Derive the queries from `business.json`** — substitute your `industry`, `business_type`, space, and region into the templates. These are advertiser-agnostic — they surface the *field*, not the known names:
```
WebSearch: new {your space} app {region} 2026 launch
WebSearch: best {your space} apps {region} 2026
WebSearch: {your space} startup {region} funding 2026
WebSearch: {your industry} {business_type} app {region} 2026
WebSearch: "{your space}" {region} Play Store new 2026
```
(e.g. if `business.json` describes a "project-management SaaS" in North America, the first query becomes `new project management app North America 2026 launch`.)

Also mine the **comparison listicles** that surface in results (e.g. "10 best {your space} apps") — they routinely name the full current field including small players.

### 2.5b — Extract & dedupe candidates
From the results, extract every distinct app / company that operates in **your product's space** (same `industry` / `business_type` / target users as `business.json`). For each candidate, capture: name, Play Store package (if findable), website, what it does, any scale/funding signal.

Cross-reference each against the **known set** in `.claude/knowledge/competitor-audit/competitors.md` (all tiers + Watchlist + Discovery Log). Drop anything already listed. What remains is **net-new**.

### 2.5c — Triage each net-new candidate
| Test | If yes → |
|------|----------|
| Operates in your space, in your market, and is real (live app or funded) | **Add to Watchlist** at minimum |
| Same core segment / target users as your product AND material (funding, multi-market, or notable installs) | **Add as Tier 1 candidate** — flag in report for user confirmation |
| Adjacent / substitute category (competes for the same customer or wallet, not a direct peer) | Add to **Watchlist** (adjacent) |
| Dead, out-of-market, or duplicate | Note in Discovery Log as "evaluated, not tracked" — do NOT add scan entries |

**Default tiering is conservative: Watchlist.** Only propose Tier 1 promotion when the model overlap with your product is strong; surface that proposal in the report's TL;DR for the user to confirm rather than auto-promoting.

### 2.5d — Self-update the reference files (the important part)
For every candidate that passes triage, **write it back this run** so it's tracked going forward:
1. **`competitors.md`** — add a profile block under the chosen tier (or Watchlist row), and append a dated row to the **Discovery Log** table (newest first): `| {date} | {what was found} | {decision} |`.
2. **`scan-urls.json`** — for anything Watchlist-or-higher with a known Play Store package, add entries to `app_store_data` (android + ios), `cross_verification` (appbrain), `ads_library` (google transparency by domain), and `news_rss` (a `"{Name}" {your space}` keyword) so the scanner covers it automatically next week. Validate the JSON parses (`python3 -c "import json,sys; json.load(open(...))"`) before finishing.
3. If a candidate can't be fully resolved (no package id yet), still log it in the Discovery Log with a `_todo` so a later run completes it.

### 2.5e — Trending detection
Beyond brand-new apps, flag **trend shifts** in the known set surfaced by discovery/news: a competitor suddenly surging in listicles/rankings, fresh funding, a viral campaign, or a new market launch. Record any such trend as a Discovery Log row AND escalate it to the report TL;DR. If a Watchlist player crosses into your core space or starts paid acquisition, propose promoting it.

### 2.5f — Report the discovery outcome
Always include a short **"Discovery This Run"** block in the report (even when nothing new):
```
## Discovery This Run
- New competitors found & added: {names + tier, or "None — field unchanged this week"}
- Trending: {any surge/funding/campaign signal, or "None"}
- Pending Tier-1 promotion (needs confirmation): {names or "None"}
```

---

## Phase 3 — News & Press (last 7 days)

### Google News RSS (primary — free, no API key)
Use WebFetch on Google News RSS feeds for each search keyword. Build keywords from `business.json` (each competitor name + your space) and the `news_rss` list in `scan-urls.json`. Use the `hl`/`gl`/`ceid` parameters that match your `business.json` region:

```
https://news.google.com/rss/search?q={URL_ENCODED_QUERY}+when:7d&hl={lang}&gl={region}&ceid={region}:{lang}
```

Keywords to search (derive from competitors[] + your space — examples with placeholders):
- `"{Competitor Name}" {your space}`
- `"{Another Competitor}" {region}`
- `"{Your Product}" {your space}`
- `"{your space}" {region} 2026`
- `"{your industry}" regulation`

Parse the RSS XML — extract: title, link, source, pubDate for each item.

### WebSearch supplement
Also run WebSearch for each Tier 1 competitor to catch anything RSS missed:
```
WebSearch: "{Competitor Name}" {your space} news 2026
WebSearch: {Another Competitor} {region} news 2026
```

**Filter to current year only** (2026, or at most 2025). Never include older results.

### Deduplicate
Merge RSS + WebSearch results, deduplicate by headline similarity.

---

## Phase 4 — Google Trends

Use WebSearch to check relative search interest (substitute your product + Tier 1 competitor names from `business.json`):
```
WebSearch: Google Trends {your product} vs {competitor A} vs {competitor B} {region} 2026
```

Also try fetching Google Trends directly (URL-encode the names, set `geo` to your region):
```
WebFetch: https://trends.google.com/trends/explore?geo={REGION}&q={your product},{competitor A},{competitor B}&date=today%203-m
```

Report the relative interest levels. If exact data isn't available, note "Trends data unavailable — manual check recommended" and provide the URL for manual inspection.

---

## Phase 5 — Feature & Pricing Signals

### From "What's New" (already collected in Phase 1-2)
Compare each competitor's "What's New" text against last week's baseline:
- **New features** — anything new in the changelog
- **Bug fixes** — volume of fixes (signals stability issues)
- **UI/UX changes** — mentioned redesigns

### From recent reviews (sentiment proxy for pricing)
Use WebSearch to find recent negative reviews mentioning pricing:
```
WebSearch: "{competitor}" app "too expensive" OR "pricing" OR "subscription" OR "charges" site:play.google.com
```

Flag any pricing complaints trending upward — this is an opportunity signal for your product.

---

## Phase 6 — Hiring Signals

**Primary: Playwright scanner** — visits LinkedIn jobs pages and WelcomeToTheJungle directly:
```bash
python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --section hiring
```
Review the screenshots at `/tmp/competitor-scan-*-linkedin_jobs.png` and `/tmp/competitor-scan-*-welcometothejungle.png`.

**Supplement with WebSearch** to catch roles not on those pages (substitute competitor names from `business.json`):
```
WebSearch: "{Competitor Name}" hiring OR jobs site:linkedin.com 2026
WebSearch: {Another Competitor} {region} hiring OR jobs site:linkedin.com 2026
```

Categorize any findings:
- **Engineering hires** = building new features
- **Data/ML hires** = investing in core algorithms (matching, pricing, ranking, etc.)
- **Sales/Enterprise hires** = B2B pivot or enterprise expansion
- **Ops/region-specific hires** = geographic expansion
- **Marketing hires** = growth push incoming

If no results found, note "No new job postings detected" — this is still signal (they're not expanding).

---

## Phase 7 — Social Media Snapshot (per-platform: Instagram + LinkedIn + X)

The audit must capture social signals **per platform** because each platform plays a different role: Instagram = visual / reels / lifestyle, LinkedIn = corporate / community / sustainability, X = real-time announcements.

### 7a — Playwright scanner (primary)
```bash
python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --section social_media
```
Review screenshots at `/tmp/competitor-scan-*-{platform}.png`. Logged-out walls block deep scrolling on Instagram and LinkedIn — when this happens, take what's visible and supplement with WebSearch.

### 7b — Per-platform content theme classification
For each Tier 1 competitor, classify the week's content into one of these **content themes** so cross-competitor patterns are visible:

| Theme | Signals |
|---|---|
| **Product / UI showcase** | Screenshots, feature highlights, demo reels |
| **Problem → solution** | Pain points your product also solves, savings/efficiency comparisons |
| **Trust / safety / support** | Help center, FAQ, "what if something goes wrong" |
| **Sustainability / impact** | Green, environment, social impact messaging |
| **Community / testimonials** | Real users, success stories, "user of the week" |
| **Lifestyle / face-based** | Creator-style videos, "day in life", relatability |
| **Corporate / enterprise** | B2B partnerships, enterprise tie-ups |

### 7c — WebSearch supplements (always run, even if Playwright succeeded)
Build these from the competitor names/handles in `business.json` (examples with placeholders):
```
WebSearch: from:@{competitorHandle} site:x.com 2026
WebSearch: "{Competitor A}" OR "{Competitor B}" {your space} site:linkedin.com 2026
WebSearch: site:instagram.com "{competitor A}" OR "{competitor B}" {region} 2026
```

For each competitor, record:
- **Instagram** — cadence (posts/week), dominant content theme(s), most-engaged post (if visible)
- **LinkedIn** — cadence, dominant theme(s), notable announcements
- **X/Twitter** — campaign or partnership announcements, complaints, viral posts

If nothing notable on a platform for a competitor: write `No significant {platform} activity this week.` — empty is signal too.

---

## Phase 7d — Ads Channel Coverage (Google / LinkedIn / Meta)

Track **which ad channels each competitor is active on this week** AND **the actual creatives running**. Channel presence is a strategic signal — Google Ads = intent / capture; LinkedIn Ads = B2B / corporate; Meta Ads = consumer / mass. Creative themes show positioning shifts.

### How — single command via the scanner

```bash
python3 .claude/skills/deep-competitor-tracker/competitor-scan.py --section ads_library
```

This iterates the `ads_library` array in `scan-urls.json` and for each URL:
- Visits the page in headless Chromium with an 8-second JS-render wait
- Captures a full-page screenshot to `/tmp/competitor-scan-ads-{tag}.png`
- Extracts the first 1,500 chars of body text (used to count active ads + identify creative themes)
- Saves a JSON record `{tag, source_url, screenshot, text_excerpt, competitor, platform}`

**The `ads_library` URL list covers (derived from `business.json` → `competitors[]` + your own domain):**
- LinkedIn Ad Library — one entry per advertiser (competitor company name) and/or a space keyword, country = your `business.json` region
- Meta Ad Library — your own page + one entry per competitor Meta page id (discovery fills in any missing page ids and writes them back to `scan-urls.json`)
- Google Ads Transparency — one entry per competitor `domain` plus your own `company.website_domain`

### Counting + theme extraction

For each result, the skill must:
1. **Read the screenshot** (Read tool) — visually count active ads and note dominant creative themes (cost-savings, instant-match, sustainability, etc.).
2. **Parse the text excerpt** — LinkedIn shows "N ads match your search criteria" near the top; Meta shows "~N परिणाम / N results"; Google shows "N ad" or "No ads found".
3. **Cross-check** — if screenshot count and text excerpt disagree, trust the screenshot.
4. **Note creative headlines** — LinkedIn shows headline text in the excerpt — capture the top 3 per competitor for theme classification.

### Output — channels-by-competitor matrix

Render the matrix in the report (one row per Tier 1 competitor from `business.json`, plus your own product):

```markdown
| Competitor | Google Ads (transparency.google.com) | LinkedIn Ads | Meta Ads (Ad Library, your region) |
|---|---|---|---|
| {Your Product} | ✅ N active | ... | ✅ N active (page id) |
| {Competitor A} | ⚠ N active | ... | ✅ N active (page id) |
| {Competitor B} | ❌ 0 active | ✅ N active | (probe pending page id) |
| {Competitor C} | ❌ 0 active | — | (probe pending page id) |
```

**Delta detection:** compare each cell to last week's `last-scan.json` `ads_channels` field. If a competitor switched ON a previously-inactive channel, escalate to TL;DR. If creative themes shifted (e.g. "{Competitor A}'s LinkedIn copy went from cost-savings to lifestyle"), call it out under the matrix.

### Phase 11 — embed screenshots in Confluence

When publishing, the skill must:
1. Upload each `/tmp/competitor-scan-ads-*.png` as an attachment via `POST {BASE}/content/{PAGE_ID}/child/attachment` (multipart `file`, header `X-Atlassian-Token: no-check`).
2. Embed in body using `<ac:image ac:height="600"><ri:attachment ri:filename="..." /></ac:image>`.
3. Group screenshots under headings: Meta Ad Library, LinkedIn Ad Library, Google Ads Transparency.
4. Always include the direct ad-library URLs as fallback links so a reader can re-verify.

This makes the "Ads Channel Coverage Matrix" section show full creative evidence — a CTO can scan the page in 3 minutes and see exactly what each competitor is running.

---

## Phase 7e — Synthesize Per-Competitor Strategic Card

For each Tier 1 competitor, compose a **4-row strategic card** mirroring the Apr-26 analysis format. This is the most important artifact in the report.

```
{Competitor name} ({android version} Android · {iOS version} iOS)

| Axis | Signal |
|---|---|
| Product update | What shipped on Android + iOS this week (with What's New text) |
| Ads direction | Active channels + creative themes |
| Social direction | Instagram theme + LinkedIn theme + cadence |
| Actionable insight for your product | Concrete recommendation derived from the above |
```

The "Actionable insight for your product" is the part the team reads first. Examples (generic — replace with your competitors and space):
- *"{Competitor A} doubled down on speed/responsiveness messaging — your product should respond with parallel positioning before they own the category in user perception."*
- *"{Competitor B}'s flexibility messaging maps directly to a gap in your product: surface your equivalent flow more visibly in the app."*
- *"{Competitor C}'s stability-only release this week is a signal of slow product iteration — an opportunity for your product to out-ship them on core features."*
- *"{Competitor D}'s new in-app Help Center is a trust-building move; audit your own support visibility (chat, FAQ, in-app help)."*

If a competitor had **zero changes** this week (no new app version, no ad activity, no social posts), the card still gets generated — just say `No change` in each axis. That's a valid card.

> Render one card per Tier 1 competitor listed in `business.json` → `competitors[]`. The examples and templates below use `{Competitor A/B/...}` placeholders — substitute the real names at runtime.

---

## Phase 8 — Manual Input (optional)

Ask the user:
```
Any competitor signals you spotted this week that I should include?
(LinkedIn posts, conference talks, word-of-mouth, partnership rumors, etc.)
Type your observations or press Enter to skip:
```

Incorporate any user input into the "Human Intelligence" section of the report.

---

## Phase 9 — Compute Deltas & Synthesize Report

### Delta computation
Compare all collected data against `last-scan.json`:
- Rating changes (highlight if delta > 0.1 in either direction)
- Install tier changes (e.g., "5M+" → "10M+")
- Version bumps (new release this week)
- New "What's New" text (feature launches)
- News volume change

### Generate the report

> Throughout the template below, `{Your Product}` = `company.product_name` from `business.json`, and `{Competitor A/B/C/...}` = the Tier 1 entries in `business.json` → `competitors[]`. Generate exactly one row/card/section per real competitor — do not invent or omit any.

```
═══════════════════════════════════════════════════════════
  {Your Product} Competitor Pulse — Week of {DATE}
  Generated: {TIMESTAMP}
═══════════════════════════════════════════════════════════

## TL;DR
- {Most important signal — one sentence} [source](url)
- {Second signal} [source](url)
- {Third signal or "No material competitive changes this week"} [source](url)

## Discovery This Run
- New competitors found & added: {names + tier, or "None — field unchanged this week"}
- Trending: {any surge/funding/campaign signal, or "None"}
- Pending Tier-1 promotion (needs confirmation): {names or "None"}

## App Store Dashboard

| App | Platform | Rating | Delta | Installs | Version | Updated | New Release? |
|-----|----------|--------|-------|----------|---------|---------|--------------|
| {Your Product} | Android | X.X | — | Xk+ | X.Y.Z | date | Yes/No |
| {Your Product} | iOS | X.X | — | — | X.Y.Z | date | Yes/No |
| {Competitor A} | Android | X.X | +/-X.X | XM+ | X.Y.Z | date | Yes/No |
| {Competitor A} | iOS | X.X | +/-X.X | — | X.Y.Z | date | Yes/No |
| {Competitor B} | Android | X.X | +/-X.X | XK+ | X.Y.Z | date | Yes/No |
| {Competitor B} | iOS | X.X | +/-X.X | — | X.Y.Z | date | Yes/No |
| ... (one Android + one iOS row per Tier 1 competitor in business.json) | | | | | | | |

## Per-Competitor Strategic Card — THIS IS THE PRIMARY ARTIFACT

For each Tier 1 competitor, include a 4-axis card. Keep the format consistent across competitors and across weeks so deltas are easy to compare.

### {Competitor A} — v{android} Android · v{ios} iOS
| Axis | Signal |
|---|---|
| Product update | {Android What's New + iOS What's New, or "No new release this week"} |
| Ads direction | {Channels active: Google / LinkedIn / Meta} · {Creative themes} |
| Social direction | Instagram: {theme + cadence} · LinkedIn: {theme + cadence} · X: {notable posts} |
| **Actionable insight for your product** | {Concrete recommendation} |

### {Competitor B} — v{android} Android · v{ios} iOS
{same structure}

### {Competitor C} — v{android} Android · v{ios} iOS
{same structure — if a competitor is global, flag global vs your-region-specific signals}

{...one card per Tier 1 competitor in business.json. For the competitor that is the closest model-match to your product, keep the actionable insight returning to your core differentiation (from company.one_liner / metrics) and target-user overlap.}

## Feature Launches This Week (cross-competitor diff)
{For each competitor that shipped an update, side-by-side Android + iOS:}
### {Competitor} — Android v{version} / iOS v{version} ({date})
**Android What's New:** {text}
**iOS What's New:** {text}
**Signal:** {What this means for your product — opportunity or threat}

{If no updates: "No competitor app updates this week."}

## Ads Channel Coverage Matrix (this week)

| Competitor | Google Ads | LinkedIn Ads | Meta Ads | Δ vs last week |
|---|---|---|---|---|
| {Competitor A} | Active/Inactive | Active/Inactive | Active/Inactive | — / +channel / -channel |
| {Competitor B} | ... | ... | ... | ... |
| ... (one row per Tier 1 competitor in business.json) | | | | |

{Below the matrix, note any creative-theme shift per competitor — e.g. "{Competitor A}'s Meta creatives now lead with 'X' vs 'Y' last week."}

## News & Press (last 7 days ONLY)
{Bulleted list — ONLY articles published in the last 7 days}
- {source}: [{headline}](url) ({date}) — {1-line interpretation}

{If no news: "No news articles found in the last 7 days for any competitor."}

## Background Context (first scan only)
{ONLY include this section on the very first scan when there is no baseline.}
{Clearly label each article with its publication date so the reader knows it's not new.}
- {Month Year} — [{headline}](url) — {why it's relevant baseline context}

## Google Trends (90-day rolling, your region)
{Relative search interest: {Your Product} vs {Competitor A} vs {Competitor B}}
{Note any trend changes — rising/falling interest}

## Hiring Signals
| Company | Roles Spotted | Signal | Source |
|---------|--------------|--------|--------|
| {Competitor A} | {roles or "None"} | {interpretation} | [LinkedIn](url) |
| {Competitor B} | {roles or "None"} | {interpretation} | [LinkedIn](url) |
| ... (one row per Tier 1 competitor) | | | |

## Social Media Activity (per platform)

### Instagram
| Competitor | Cadence | Dominant theme(s) | Notable post |
|---|---|---|---|
| {Competitor A} | X posts/week | {theme(s)} | {link or "—"} |
| {Competitor B} | ... | ... | ... |
| ... (one row per Tier 1 competitor) | | | |

### LinkedIn
| Competitor | Cadence | Dominant theme(s) | Notable post |
|---|---|---|---|
| {Competitor A} | X posts/week | {theme(s)} | {link or "—"} |
| {Competitor B} | ... | ... | ... |
| ... (one row per Tier 1 competitor) | | | |

### X / Twitter
{2-3 bullet points of notable activity, or "No significant activity this week"}

## User Sentiment (from reviews)
### {Competitor A} — Recent Complaints
{Top 2-3 negative review themes — these are opportunities for your product}

### {Competitor B} — Recent Complaints
{Top 2-3 negative review themes}

{...one block per Tier 1 competitor. For the closest model-match competitor, frame their recurring complaints as your product's differentiation talking points.}

### {Your Product} — Our Recent Reviews
{Top 2-3 themes in our reviews — what users love/hate}

{If --full, include Tier 2 competitors here}

## Human Intelligence
{User-provided observations from Phase 8, or "None this week"}

## Key-Competitor Watch (optional standing section)
{If business.json flags a competitor that warrants a dedicated tracker — e.g. a large
 global player entering your market — keep a standing block on their region-specific moves:}
- Office/Presence: {Any local office/expansion news}
- Team: {Region-specific hiring}
- Campaigns: {Local marketing}
- Regulatory: {Any relevant regulation news in your space}

## Strategic Interpretation
{1-2 paragraphs: What does this week's data mean for your product's positioning?
 What should we do about it? Be specific and actionable.}

## Recommended Actions
| # | Action | Owner | Priority | Rationale |
|---|--------|-------|----------|-----------|
| 1 | {Specific action} | {owner from team.json} | High/Med/Low | {Why} |
| 2 | {Specific action} | ... | ... | ... |

═══════════════════════════════════════════════════════════
```

---

## Phase 10 — Save Baseline & Persist

### Save current scan as next week's baseline
Write the structured data (ratings, versions, install counts, "What's New" text, scan date) to:
```
.claude/knowledge/competitor-audit/last-scan.json
```

Format:
Use one key per competitor, keyed by the `name` from `business.json` → `competitors[]` (plus `self` for your own product). The keys below are placeholders:

```json
{
  "scan_date": "2026-05-05",
  "competitors": {
    "self":         { "android_rating": 4.2, "android_installs": "500K+", "android_version": "X.Y.Z", "android_updated": "date", "android_whats_new": "text", "ios_rating": 4.1, "ios_version": "X.Y.Z", "ios_whats_new": "text" },
    "competitor_a": { "android_rating": "...", "ios_rating": "...", "ads_channels": {"google_ads":"active","linkedin_ads":"active","meta_ads":"active"}, "social_themes": {"instagram":"product/UI","linkedin":"corporate/sustainability"} },
    "competitor_b": { "android_rating": "...", "ios_rating": "...", "ads_channels": {}, "social_themes": {} }
  },
  "news_headlines": ["headline 1", "headline 2"],
  "trends_snapshot": "description of relative interest",
  "discovery": {
    "new_competitors_added": ["{name (tier)}"],
    "trending": ["{surge/funding/campaign signal}"],
    "pending_tier1_promotion": ["{name}"]
  },
  "strategic_response": {
    "vs_competitor_a": "{insight}",
    "vs_competitor_b": "{insight}"
  }
}
```

Persisting `ads_channels` and `social_themes` per competitor enables WoW delta detection on positioning (e.g. "{Competitor A}'s Meta creatives shifted from savings to flexibility this week").

### Save the report
Write the full report to:
```
reports/competitor-audit/competitor-pulse-{YYYY-MM-DD}.md
```

### Display summary
Print the TL;DR and Recommended Actions sections to the terminal for immediate visibility.

---

## Phase 11 — Publish to Confluence

Publish the report as a Confluence page under the **Competitor Pulse** parent page in your Confluence space.

### Confluence Configuration

```
CONFLUENCE_CLOUD_ID = ${CONFLUENCE_CLOUD_ID}
CONFLUENCE_BASE     = https://api.atlassian.com/ex/confluence/{CLOUD_ID}/wiki/rest/api
PARENT_PAGE_ID      = ${CONFLUENCE_PARENT_PAGE_ID}   # "Competitor Pulse" parent page in your Confluence space
SPACE_ID            = ${CONFLUENCE_SPACE_KEY}   # your Confluence space
```

Authentication: use `ATLASSIAN_EMAIL` and `ATLASSIAN_API_TOKEN` from `.env` with HTTP Basic Auth.

### Page title format
```
Competitor Pulse — Week of {YYYY-MM-DD}
```

### Convert report to Confluence storage format

Build the HTML body using Confluence storage format. Map each report section to HTML:

```html
<!-- TL;DR as info panel -->
<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">TL;DR</ac:parameter>
  <ac:rich-text-body>
    <ul>
      <li><strong>{signal 1}</strong></li>
      <li>{signal 2}</li>
      <li>{signal 3}</li>
    </ul>
  </ac:rich-text-body>
</ac:structured-macro>

<!-- App Store Dashboard as styled table -->
<h2>App Store Dashboard</h2>
<table>
  <tbody>
    <tr>
      <th>App</th><th>Platform</th><th>Rating</th><th>Delta</th>
      <th>Installs</th><th>Version</th><th>Updated</th><th>New Release?</th>
    </tr>
    <tr><td>{Your Product}</td><td>Android</td><td>X.X</td><!-- ... --></tr>
    <!-- ... rows ... -->
  </tbody>
</table>

<!-- Feature Launches — use expand macro per competitor -->
<h2>Feature Launches This Week</h2>
<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">{Competitor} — v{version} ({date})</ac:parameter>
  <ac:rich-text-body>
    <p><em>{Full "What's New" text}</em></p>
    <ac:structured-macro ac:name="note">
      <ac:rich-text-body><p><strong>Signal:</strong> {interpretation}</p></ac:rich-text-body>
    </ac:structured-macro>
  </ac:rich-text-body>
</ac:structured-macro>

<!-- News & Press — bullet list -->
<h2>News &amp; Press (7 days)</h2>
<ul>
  <li><strong>{source}</strong>: <a href="{link}">{headline}</a> — {interpretation}</li>
</ul>

<!-- Hiring Signals — table -->
<h2>Hiring Signals</h2>
<table>
  <tbody>
    <tr><th>Company</th><th>Roles Spotted</th><th>Signal</th></tr>
    <tr><td>{company}</td><td>{roles}</td><td>{signal}</td></tr>
  </tbody>
</table>

<!-- Key-Competitor Watch — warning panel (optional, only if business.json flags one) -->
<h2>Key-Competitor Watch</h2>
<ac:structured-macro ac:name="warning">
  <ac:parameter ac:name="title">{Competitor} Tracker</ac:parameter>
  <ac:rich-text-body>
    <table>
      <tbody>
        <tr><th>Area</th><th>Status</th></tr>
        <tr><td>Office/Presence</td><td>{status}</td></tr>
        <tr><td>Team</td><td>{status}</td></tr>
        <tr><td>Regulatory</td><td>{status}</td></tr>
        <tr><td>Revenue</td><td>{status}</td></tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>

<!-- Strategic Interpretation — paragraphs -->
<h2>Strategic Interpretation</h2>
<p>{interpretation paragraphs}</p>

<!-- Recommended Actions — table with status lozenges for priority -->
<h2>Recommended Actions</h2>
<table>
  <tbody>
    <tr><th>#</th><th>Action</th><th>Owner</th><th>Priority</th><th>Rationale</th></tr>
    <tr>
      <td>1</td><td>{action}</td><td>{owner}</td>
      <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Red</ac:parameter><ac:parameter ac:name="title">CRITICAL</ac:parameter></ac:structured-macro></td>
      <td>{rationale}</td>
    </tr>
  </tbody>
</table>

<!-- Footer -->
<hr/>
<p><em>Generated by AI-PM Operator /competitor-tracker — {TIMESTAMP}</em></p>
```

**Priority → status lozenge color mapping:**
- CRITICAL → Red
- HIGH → Yellow
- MEDIUM → Blue
- LOW → Grey

### Publish via REST API

Use `python3 -c` or `curl` to call the Confluence REST API directly (same pattern as `tools/weekly-performance-report.py`):

```python
import requests, os, json
from requests.auth import HTTPBasicAuth

CLOUD_ID  = "${CONFLUENCE_CLOUD_ID}"
BASE      = f"https://api.atlassian.com/ex/confluence/{CLOUD_ID}/wiki/rest/api"
PARENT_ID = "${CONFLUENCE_PARENT_PAGE_ID}"
SPACE_ID  = "${CONFLUENCE_SPACE_KEY}"
auth      = HTTPBasicAuth(os.environ["ATLASSIAN_EMAIL"], os.environ["ATLASSIAN_API_TOKEN"])
headers   = {"Accept": "application/json", "Content-Type": "application/json"}

title = "Competitor Pulse — Week of {DATE}"

# Check if page exists
resp = requests.get(f"{BASE}/content", params={"title": title, "expand": "version", "limit": 5},
                     auth=auth, headers=headers, timeout=15)
results = resp.json().get("results", [])

if results:
    page = results[0]
    payload = {
        "version": {"number": page["version"]["number"] + 1},
        "title": title, "type": "page",
        "body": {"storage": {"representation": "storage", "value": html_body}}
    }
    resp = requests.put(f"{BASE}/content/{page['id']}", json=payload, auth=auth, headers=headers, timeout=30)
else:
    payload = {
        "type": "page", "title": title,
        "space": {"id": int(SPACE_ID)},
        "ancestors": [{"id": int(PARENT_ID)}],
        "body": {"storage": {"representation": "storage", "value": html_body}}
    }
    resp = requests.post(f"{BASE}/content", json=payload, auth=auth, headers=headers, timeout=30)

resp.raise_for_status()
page_data = resp.json()
web_url = page_data.get("_links", {}).get("base", "https://your-domain.atlassian.net/wiki") + page_data.get("_links", {}).get("webui", "")
print(f"Published: {web_url}")
```

### Output

After publishing, print:
```
Confluence: {page_url}
```

---

## Output Rules

1. **Every claim must have a citation link.** No exceptions. Every data point, every finding, every number must link to its source URL. In the markdown report, use `[source](url)`. In Confluence HTML, use `<a href="url">source</a>`. If a data point can't be sourced, mark it `[unverified]` explicitly.
2. **News section is strictly last 7 days.** Only include articles published in the last 7 days. If this is the first scan and background context is needed, put it in a separate "Background Context (first scan only)" section clearly labeled as NOT from this week.
3. **Current year filter** — all WebSearch queries MUST include `2026` or `when:7d`. Never surface results from 2024 or earlier.
4. **No fabrication** — if a data point can't be fetched, say "Data unavailable" not a guess. If a Play Store page was truncated, say "Play Store truncated" — don't omit the column.
5. **Global-app caveat** — if any tracked competitor uses a single global app/listing, note that its install counts and ratings reflect worldwide usage, not your region. Add region-specific MAU/usage from credible sources where available, and flag the caveat in every report.
6. **Never trust reference files as ground truth** — `competitors.md` contains hints, not verified data. Every number (installs, ratings, scale claims) MUST be verified against the actual source during each scan. If Play Store data is truncated, cross-check with AppBrain (`https://www.appbrain.com/app/{package_id}`) or Sensor Tower. Note the verification source. If unverifiable, mark `[unverified]`.
7. **Actionable > Informational** — every finding should end with "so what?" for your product.
8. **3-minute read** — the full report should take under 3 minutes to scan. Cut ruthlessly.
9. **Date context on background articles** — when citing articles, always include the publication month/year so the reader knows how fresh the information is. Mark stale articles (>3 months old) explicitly.
