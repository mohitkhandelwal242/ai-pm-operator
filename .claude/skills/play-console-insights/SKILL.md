---
name: play-console-insights
description: "Play Store ASO audit — pulls installs, store-listing CVR, search-term acquisition, vitals, and live store-listing experiments. Combines Play Console reports bucket + Play Developer Reporting API + Product DB install funnel. Diff vs prior run, flag anomalies (CVR drop, install >20% delta, keyword shifts, experiment moves), publish to Confluence. Use when asked about ASO, Play Store performance, store listing experiments, Play Store CVR, search terms, or '/audit-aso'."
---

# /audit-aso — Play Store ASO Audit

Weekly audit of Product's Google Play Store presence. Combines:

1. **Play Console reports bucket** (`gs://pubsite_prod_rev_*/`) — daily CSVs for installs, acquisition by search term, store-listing visitors → installers CVR, country breakdown
2. **Play Developer Reporting API** — vitals (crash rate, ANR rate, slow rendering) — degraded vitals tank Play Store ranking and CVR
3. **Play Developer Publishing API** (`androidpublisher.googleapis.com`) — store-listing experiments (best-effort; falls back to manual YAML if endpoint unavailable)
4. **Product production DB** — install → paid-sub funnel scoped to Organic / Google-Play channels (via `/install-funnel`)

Produces console summary + Confluence report + Jira comment. Stores a snapshot per run in `.context/channel-audits/aso/` so the next run can diff and flag anomalies.

---

## Prerequisites

Environment variables (from `.env`):

```
# OAuth2 — same client may be reused for Google Ads (scope is what differs)
GOOGLE_PLAY_CLIENT_ID=<oauth2 client id>
GOOGLE_PLAY_CLIENT_SECRET=<oauth2 client secret>
GOOGLE_PLAY_REFRESH_TOKEN=<long-lived refresh token>

# App
GOOGLE_PLAY_PACKAGE_NAME=${ANDROID_PACKAGE_NAME}            # Product Android applicationId (verified in product-android/app/build.gradle)

# Reports bucket — copy from Play Console → Download reports → Copy Cloud Storage URI
# Begins with `pubsite_prod_rev_<digits>`
GOOGLE_PLAY_REPORTS_BUCKET=pubsite_prod_rev_XXXXXXXXXXXXX

# Reused
SSH_KEY_PATH=                # DB tunnel for /install-funnel
ATLASSIAN_EMAIL=
ATLASSIAN_API_TOKEN=
CONFLUENCE_SPACE_KEY=${CONFLUENCE_SPACE_KEY}
```

Required OAuth2 scopes (request all when generating the refresh token):

- `https://www.googleapis.com/auth/androidpublisher` — Publishing API (experiments, listings)
- `https://www.googleapis.com/auth/playdeveloperreporting` — Reporting API (vitals)

**Cloud Storage (reports bucket) uses a separate auth path.** `gsutil` and `gcloud storage` consume Application Default Credentials, not the OAuth2 refresh token we generated for the REST APIs. Set this up once:

```bash
# Option A — user creds (interactive, one-time)
gcloud auth login
gcloud auth application-default login

# Option B — service account (preferred for headless / Cronicle)
# Grant the SA `storage.objectViewer` on the reports bucket, then:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
```

> **First run gate:** if any `GOOGLE_PLAY_*` env var is missing, OR if `gsutil ls "gs://$GOOGLE_PLAY_REPORTS_BUCKET/" | head -1` returns auth error, print the setup checklist at the bottom of this file and exit cleanly. Do not try to partially run.

Local tools: `gsutil` (or `gcloud storage`) must be on PATH. `curl`, `python3`, `jq` are assumed.

---

## Arguments

| Argument | Action |
|----------|--------|
| *(empty)* / `weekly` | Last 7 days — full audit, Confluence report |
| `30d` / `monthly` | Last 30 days |
| `90d` / `quarterly` | Last 90 days — strategic recommendations |
| `experiments` | Live experiment status only — quick check |
| `keywords` | Search-term acquisition only |
| `vitals` | Crash / ANR / slow-render only — when CVR drops and you suspect quality |
| `compare` | Run all 3 ad audits + ASO and compare channels |

---

## Execution Steps

### Step 1 — Set Date Range

| Arg | Since | Until |
|-----|-------|-------|
| `weekly` / empty | 7 days ago | yesterday |
| `30d` / `monthly` | 30 days ago | yesterday |
| `90d` / `quarterly` | 90 days ago | yesterday |

> Play Console data lags by ~24h. Always use *yesterday* as the upper bound — `today` will return partial rows.

### Step 2 — Refresh OAuth2 Access Token

```bash
source .env
ACCESS_TOKEN=$(curl -s -X POST https://oauth2.googleapis.com/token \
  -d "client_id=$GOOGLE_PLAY_CLIENT_ID" \
  -d "client_secret=$GOOGLE_PLAY_CLIENT_SECRET" \
  -d "refresh_token=$GOOGLE_PLAY_REFRESH_TOKEN" \
  -d "grant_type=refresh_token" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

Refresh tokens don't expire; access tokens last 1 hour — refresh each run.

### Step 3 — Collect Data (Parallel)

Run all six fetches in parallel; assemble after all complete.

#### 3a. DB Install Funnel — Google-Play / Organic split

```bash
source .env && python3 tools/meta-install-funnel.py {since} {until}
```

Extract:

- `Organic` row → installs that landed via Play Store browse/search (no paid-ad mediaSource)
- Conversion rates: Inst→Sign, Sign→Pref, Pref→Paid, Inst→Paid
- Revenue from Organic channel

These rows are the **organic ASO funnel** — what ASO actually delivers. Paid-channel installs (Meta, Google Ads) bypass ASO and live in their own audits.

> Note: in `tools/meta-install-funnel.py` the `Organic` channel bucket = Play Store search + Play Store browse + deep links + unattributed installs. It is a superset of "ASO" strictly defined (search + browse only), so treat the Organic row as a directional ASO signal, not a precise one. The store-listing CVR in Step 3c is the cleaner ASO metric.

#### 3b. Reports Bucket — Installs (overview)

```bash
# Portable date → YYYYMM (works on macOS + Linux + Cronicle hosts)
SINCE_MONTH=$(python3 -c "from datetime import date; print(date.fromisoformat('{since}').strftime('%Y%m'))")
UNTIL_MONTH=$(python3 -c "from datetime import date; print(date.fromisoformat('{until}').strftime('%Y%m'))")
PKG=$GOOGLE_PLAY_PACKAGE_NAME

mkdir -p .context/channel-audits/aso/_raw

# Loop through all months in range (bucket files are partitioned by month)
gsutil -m cp "gs://$GOOGLE_PLAY_REPORTS_BUCKET/stats/installs/installs_${PKG}_*_overview.csv" \
  .context/channel-audits/aso/_raw/
```

Parse each CSV — columns: `Date, Package Name, Daily Device Installs, Daily Device Uninstalls, Daily Device Upgrades, Active Device Installs, …` — filter rows where `Date` ∈ [since, until].

Compute per-day:

- daily_installs, weekly_installs (7d rolling), active_installs (latest)
- install velocity (Δ/day vs prior period)

#### 3c. Reports Bucket — Acquisition by Search Term (THE keyword report)

```bash
# Acquisition CSVs are organized by report_type, then dimensioned
gsutil -m cp "gs://$GOOGLE_PLAY_REPORTS_BUCKET/acquisition/play_country/play_country_${PKG}_*_*.csv" \
  .context/channel-audits/aso/_raw/
gsutil -m cp "gs://$GOOGLE_PLAY_REPORTS_BUCKET/acquisition/play_search/play_search_${PKG}_*_*.csv" \
  .context/channel-audits/aso/_raw/
gsutil -m cp "gs://$GOOGLE_PLAY_REPORTS_BUCKET/acquisition/store_listing/store_listing_${PKG}_*_*.csv" \
  .context/channel-audits/aso/_raw/
```

Key columns in `play_search_*.csv`:

- `Date, Search Term, Store Listing Visitors, Installers, Conversion Rate (%)`

For the window:

1. Aggregate visitors + installers per `Search Term` → compute true CVR = installers / visitors
2. Rank by `Installers DESC` → top 20 keywords driving installs
3. Rank by `Visitors DESC, CVR ASC` → keywords with traffic but **poor** conversion (ASO opportunity)
4. Diff vs `prior_run.json` → flag any term that **dropped > 30%** in installers or **disappeared from top 20**

Key columns in `store_listing_*.csv`:

- `Date, Store Listing Visitors, Installers, Conversion Rate (%)` — these are **all visitors** (paid + organic + deep links)
- Compute period CVR. This is the **headline ASO metric** because Play Store decides ranking partly on this.

#### 3d. Reports Bucket — Ratings

```bash
gsutil -m cp "gs://$GOOGLE_PLAY_REPORTS_BUCKET/stats/ratings/ratings_${PKG}_*_overview.csv" \
  .context/channel-audits/aso/_raw/
```

Pull `Average Rating` and `Daily Ratings 1..5 Stars` per day. Aggregate over window. Flag if rating dropped > 0.1 stars vs prior run — this directly hurts CVR.

#### 3e. Play Developer Reporting API — Vitals

```bash
# Crash rate
curl -s -X POST \
  "https://playdeveloperreporting.googleapis.com/v1beta1/apps/$GOOGLE_PLAY_PACKAGE_NAME/crashRateMetricSet:query" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["crashRate", "userPerceivedCrashRate"],
    "timelineSpec": {
      "aggregationPeriod": "DAILY",
      "startTime": {"year": YYYY, "month": MM, "day": DD, "timeZone": {"id": "Asia/Calcutta"}},
      "endTime":   {"year": YYYY, "month": MM, "day": DD, "timeZone": {"id": "Asia/Calcutta"}}
    }
  }'

# ANR rate
curl -s -X POST \
  "https://playdeveloperreporting.googleapis.com/v1beta1/apps/$GOOGLE_PLAY_PACKAGE_NAME/anrRateMetricSet:query" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "metrics": ["anrRate", "userPerceivedAnrRate"], "timelineSpec": {...} }'

# Slow rendering (optional)
curl -s -X POST \
  "https://playdeveloperreporting.googleapis.com/v1beta1/apps/$GOOGLE_PLAY_PACKAGE_NAME/slowRenderingRateMetricSet:query" \
  ...
```

Parse `rows[].metrics` → average crash / ANR / slow-render % for the window. Compare vs Play's "bad behavior threshold" (crash rate 1.09%, ANR rate 0.47% as of 2026).

#### 3f. Store-Listing Experiments — best-effort live fetch, fall back to YAML

**Attempt 1 — Publishing API:**

```bash
# Experiments live under storeListings.localizedExperiments — endpoint surface is
# in flux. Try the documented path first; on 404/403 fall back to YAML.
curl -s -w "\n%{http_code}" \
  "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/$GOOGLE_PLAY_PACKAGE_NAME/experiments" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

If HTTP 200: parse each experiment → `name, status (RUNNING|APPLIED|REJECTED), variants[].name, variants[].installersCount, variants[].cvr`. Compute winner uplift vs control.

**Attempt 2 — Manual YAML fallback:**

If the API returns 404/403, read `.context/channel-audits/aso/experiments.yaml`:

```yaml
# .context/channel-audits/aso/experiments.yaml
experiments:
  - name: "Icon-Sept-v2"
    status: RUNNING        # RUNNING | APPLIED | REJECTED | DRAFT
    started_at: 2026-04-22
    hypothesis: "Brighter red icon increases CTR from search results"
    variants:
      - name: control
        traffic_pct: 50
      - name: variant_A
        traffic_pct: 50
```

For each `RUNNING` experiment, query the DB for installs in the experiment window and compare against the prior 30-day baseline. Note: we can't split visitors vs installers per variant from outside Play Console, so YAML-based attribution is approximate — flag this clearly in the report.

### Step 4 — Compare vs Prior Run

```bash
PRIOR=$(ls -t .context/channel-audits/aso/run_*.json 2>/dev/null | head -1)
```

If a prior run exists, compute deltas:

- Install volume: `(this_period - prior_period) / prior_period × 100`
- Store-listing CVR: percentage-point change
- Average rating: absolute change
- Crash rate / ANR rate: percentage-point change
- Top-20 keywords: set difference (entered / exited / moved)
- Experiments: status transitions, new experiments, completed experiments

### Step 5 — Anomaly Flags

Apply these thresholds — anything that fires goes into the **🚩 Anomalies** section of the report:

| Flag | Threshold |
|------|-----------|
| Install volume drop | ≥ 20% week-over-week |
| Install volume spike | ≥ 30% WoW (good news, but also worth investigating) |
| Store-listing CVR drop | ≥ 1.0 pp (e.g. 18% → 17%) |
| Rating drop | ≥ 0.1 star average drop in window |
| Crash rate spike | > 1.09% (Play "bad behavior" threshold) |
| ANR rate spike | > 0.47% |
| Keyword loss | A previously top-20 keyword dropped > 30% in installers or exited top-20 |
| Keyword gain | New top-20 keyword (worth amplifying in metadata) |
| Experiment moved | Any experiment changed status (RUNNING → APPLIED/REJECTED) since last run |
| Experiment stalled | RUNNING for > 30 days without statistical decision |

### Step 6 — Recommendations

Based on data patterns:

| Pattern | Recommendation |
|---------|---------------|
| CVR dropped + rating dropped | Investigate recent reviews; rating drag is the likely cause |
| CVR dropped + rating stable + crash up | Crash regression — file a P1 backend/mobile ticket |
| CVR dropped + everything stable | Test new screenshots / short description (start an experiment) |
| Keyword X has > 1000 visitors but CVR < 5% | Listing doesn't match search intent for X — refine metadata |
| New top-20 keyword | Add to short / full description to amplify |
| Experiment has > 95% confidence + winner | Apply it; close experiment |
| Experiment RUNNING > 30 days, no decision | Likely underpowered — either kill or pause low-volume variants |
| Crash rate > Play threshold | Halt new feature work, address vitals — Play ranks you down |
| ANR rate > Play threshold | Same — vitals trump features for ranking |
| Organic install→paid CVR drops vs paid channels | Onboarding leak (not ASO); flag to product |

### Step 7 — Snapshot This Run

Write `.context/channel-audits/aso/run_{YYYY-MM-DD}.json`:

```json
{
  "run_date": "2026-05-11",
  "window": {"since": "2026-05-04", "until": "2026-05-10"},
  "installs": {"total": ..., "daily_avg": ..., "active": ...},
  "store_listing": {"visitors": ..., "installers": ..., "cvr_pct": ...},
  "rating": {"average": 4.3, "ratings_count": ...},
  "vitals": {"crash_rate_pct": 0.71, "anr_rate_pct": 0.18, "slow_render_pct": ...},
  "top_keywords": [{"term": "{example keyword}", "installers": ..., "cvr_pct": ...}, ...],
  "experiments": [{"name": "Icon-Sept-v2", "status": "RUNNING", "started_at": "...", "variants": [...]}],
  "db_funnel": {"organic": {"installs": ..., "paid_subs": ..., "revenue": ...}},
  "anomalies": [...],
  "recommendations": [...]
}
```

Keep the last 12 runs (~3 months); delete older snapshots to keep `.context/` tidy.

### Step 8 — Publish

#### Console output

```
====================================================================
  /audit-aso — {since} → {until}
====================================================================

  Installs        45,212   ▲ +4.1% WoW
  Store CVR        18.2%   ▼ -0.6pp WoW
  Rating            4.3 ★  ─ flat
  Crash rate       0.71%   ✅ under 1.09% threshold
  ANR rate         0.18%   ✅ under 0.47% threshold

  Top keywords (by installers)
    1. {keyword A}             4,212  CVR 22.1%
    2. {keyword B}             2,891  CVR 19.4%
    ...

  🚩 Anomalies (2)
    - Store-listing CVR dropped 0.6pp (18.8% → 18.2%)
    - Keyword "{keyword C}" exited top-20 (4,100 → 2,300 installers)

  Live experiments (1)
    - Icon-Sept-v2 — RUNNING (day 19) — control 17.8% / variant_A 19.4% CVR

  Recommendations (3)
    - Apply Icon-Sept-v2 to all listings — variant_A winning at >95% CI
    - Investigate "{keyword C}" keyword drop — recent metadata change?
    - Test new feature graphic — CVR plateau over 3 weeks
```

#### Confluence report (weekly / monthly / quarterly)

Publish to your Confluence space (`CONFLUENCE_SPACE_KEY`). Title: `Play Store ASO Audit — {YYYY-MM-DD} ({window})`.

**Idempotency:** search the space for an existing page with the same title; if found, PUT-update; else POST-create.

```bash
EXISTING=$(curl -s -u "$ATLASSIAN_EMAIL:$ATLASSIAN_API_TOKEN" \
  "https://your-domain.atlassian.net/wiki/api/v2/spaces/$CONFLUENCE_SPACE_KEY/pages?title=Play+Store+ASO+Audit+...&limit=1")
# branch on whether $EXISTING.results is empty
```

Include in the page (HTML storage format):

1. Executive summary table
2. Install + CVR trend chart (use Confluence chart macro or render PNG + attach)
3. Top + bottom 20 keywords table
4. Vitals table with thresholds
5. Live experiments table
6. 🚩 Anomalies panel (red)
7. Recommendations panel (info)

#### Jira comment (when this skill is triggered from a ticket context, e.g. ${PROJECT_KEY}-15366)

Post a short markdown summary with a link to the Confluence page. Include `MK_AA` revenue framing line for any `june_goal` (strategy) or `june_execution` (tactical) labeled parent.

---

## Key Constants

| Constant | Value |
|----------|-------|
| Play package name | `$GOOGLE_PLAY_PACKAGE_NAME` (`${ANDROID_PACKAGE_NAME}`) |
| Reports bucket | `gs://$GOOGLE_PLAY_REPORTS_BUCKET/` |
| Publishing API base | `https://androidpublisher.googleapis.com/androidpublisher/v3` |
| Reporting API base | `https://playdeveloperreporting.googleapis.com/v1beta1` |
| OAuth2 scopes (REST APIs) | `androidpublisher` + `playdeveloperreporting` |
| Cloud Storage auth | ADC via `gcloud auth application-default login` OR `GOOGLE_APPLICATION_CREDENTIALS` |
| Snapshot dir | `.context/channel-audits/aso/` |
| Confluence space | `${CONFLUENCE_SPACE_KEY}` (from .env) |
| DB funnel tool | `tools/meta-install-funnel.py` (Organic row = ASO channel) |

---

## Benchmarks (as of May 2026)

Use as comparison baselines — refresh quarterly.

| Metric | Account baseline | Good | Great |
|--------|-----------------|------|-------|
| Store-listing CVR | 18% | > 22% | > 28% |
| Average rating | 4.3 ★ | > 4.5 | > 4.7 |
| Daily organic installs | ~600 | > 800 | > 1,200 |
| Crash rate | 0.71% | < 0.5% | < 0.2% |
| ANR rate | 0.18% | < 0.15% | < 0.08% |
| Organic Pref→Paid | 8% | > 12% | > 18% |

> ⚠️ These numbers are **illustrative placeholders** — replace the "Account baseline" column with the actual values from your first `/audit-aso quarterly` run before you start treating anomaly flags as truth.

> ASO is a slow-moving lever. Don't expect WoW swings; track 4-week rolling averages.

---

## When to Run

- **Weekly** (`/audit-aso weekly`) — default cadence, scheduled via routine
- **After a store-listing change** — to validate impact 7+ days later
- **After a release** — to catch crash regressions before they tank CVR
- **Quarterly** (`/audit-aso quarterly`) — strategic recommendations + action tickets

---

## Routine Integration

Already wired into `.claude/knowledge/routines.md`:

```yaml
- id: audit-aso-weekly
  name: "Play Store ASO weekly audit"
  skill: "/audit-aso weekly"
  owner: MK
  schedule: Mondays, morning
  condition: if not run this week
  action: "Run /audit-aso weekly — installs, CVR, keywords, vitals, experiments"
  effort: S
```

---

## Setup Checklist (one-time)

Before the first run:

1. [ ] In Play Console → Settings → API access → enable Google Play Android Developer API, link a Google Cloud project
2. [ ] Create an OAuth2 client (Desktop) at https://console.cloud.google.com/apis/credentials
3. [ ] Enable these APIs in the cloud project:
       - Google Play Android Developer API
       - Google Play Developer Reporting API
       - Cloud Storage API
4. [ ] Run a one-time OAuth2 flow with the REST-API scopes to get `GOOGLE_PLAY_REFRESH_TOKEN`:
       ```
       androidpublisher  playdeveloperreporting
       ```
5. [ ] Wire up Cloud Storage auth (separate from OAuth2 — `gsutil` doesn't consume bearer tokens):
       ```bash
       # Interactive (one-time, per-machine):
       gcloud auth login && gcloud auth application-default login
       # OR service-account (preferred for Cronicle / CI):
       export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json   # grant storage.objectViewer on the bucket
       ```
6. [ ] Find your reports bucket: Play Console → Download reports → any report → Copy Cloud Storage URI → strip `gs://` and trailing path → that's `GOOGLE_PLAY_REPORTS_BUCKET`
7. [ ] Add all `GOOGLE_PLAY_*` vars to both `.env` and `.env.example` (template with empty values)
8. [ ] Sanity test: `gsutil ls "gs://$GOOGLE_PLAY_REPORTS_BUCKET/stats/installs/" | head` — should list files
9. [ ] Sanity test: `curl -H "Authorization: Bearer $ACCESS_TOKEN" "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/$GOOGLE_PLAY_PACKAGE_NAME/edits" -X POST -d '{}' | head` — should return an editId (or a known auth error if scopes are wrong)
10. [ ] Run `/audit-aso weekly` — verify each of Steps 3a–3f returns data
11. [ ] If experiments endpoint returns 404/403, create `.context/channel-audits/aso/experiments.yaml` per the schema in Step 3f

---

## References

Related Jiras (parent epic ${PROJECT_KEY}-15277 — ASO):

- **${PROJECT_KEY}-15366** — this skill (parent ticket)
- **${PROJECT_KEY}-15298** — Audit ASO (one-off)
- **${PROJECT_KEY}-15050** — Implement ASO changes
- **${PROJECT_KEY}-15302** — ASO doc refresh
- **${PROJECT_KEY}-15032** — Play Console API integration (was on-hold; this skill now uses it directly)

Related skills:

- `/install-funnel` — DB-side acquisition funnel; this skill reuses its Organic row
- `/funnel` — top-of-funnel install attribution
- `/audit-meta`, `/audit-google-ads` — paid-channel counterparts; together they form the full acquisition picture
- `/competitor-audit` — competitor ASO signals (rating, ranking history)
