<!--
  AUTO-GENERATED TEMPLATE — DO NOT TREAT AS GROUND TRUTH.
  This file is created/overwritten by `/operator-onboarding` and self-updated by
  `/competitor-tracker` (Phase 2.5 Discovery). It holds a working registry of the
  competitors named in `business.json` → `competitors[]`, plus any new entrants the
  tracker discovers.

  The single block below is a NEUTRAL EXAMPLE so the schema is clear. Replace it with
  your real competitors. Tier classification: Tier 1 = must track every scan,
  Tier 2 = monitor, Watchlist = adjacent/indirect (lighter cadence).

  NOTE: every number here is a hint, never verified data. Each scan must re-verify
  installs/ratings/scale against the live source.
-->

# Competitor Reference

> Source of truth for *who* to track is `business.json` → `competitors[]`. This file
> mirrors that list with per-competitor detail and is extended by the discovery pass.

## Your Product (us — baseline)

| Field | Value |
|-------|-------|
| Play Store | _(from `business.json` → `competitors[]` self entry, or your own package)_ |
| App Store | _(your iOS app id)_ |
| Website | _(your `company.website_domain`)_ |
| Twitter/X | — |
| LinkedIn | — |
| Instagram | — |
| Focus | _(your `company.one_liner` / `industry` / `business_type`)_ |

## Tier 1 — Direct, Active, Material Threat

> Populated from `business.json` → `competitors[]` where `tier == "tier1"`.
> Below is a single generic example showing the expected fields.

### Example Competitor

| Field | Value |
|-------|-------|
| Play Store | `com.example.app` |
| App Store | `id000000000` |
| Website | competitor.example.com |
| Twitter/X | @examplecompetitor |
| LinkedIn | linkedin.com/company/example-competitor |
| Instagram | @examplecompetitor |
| Focus | _(what this competitor does, in your space)_ |
| Scale | _(installs / users — verify each scan)_ |
| Ad channels (observed) | _(Google Ads / LinkedIn Ads / Meta Ads — verify each scan)_ |
| Social style | _(content themes observed)_ |
| Positioning | _(their core value-prop / messaging)_ |

## Tier 2 — Active, Smaller Scale

> Populated from `business.json` → `competitors[]` where `tier == "tier2"`. No example
> rows shipped — the discovery pass and onboarding fill this in.

## Watchlist — Adjacent / Indirect (lighter cadence)

Players that aren't direct competitors but compete for the same customer/wallet. Track
at a lighter cadence; **promote to a full tier if any moves into your core space.**

| Player | Category | Overlap with your product | Cadence |
|--------|----------|---------------------------|---------|
| _(example adjacent player)_ | _(substitute category)_ | _(why they overlap)_ | Monthly/Quarterly |

## Discovery Log

> The skill runs a **Competitor Discovery** pass each scan (Phase 2.5) and writes any new
> findings here automatically, newest first. Each entry: date, what was found, and the
> tiering decision. This is how the tracked set stays current without manual edits.

| Date | Discovery | Decision |
|------|-----------|----------|
| _(none yet)_ | _(first run will populate this)_ | _(—)_ |

## Search Keywords for News

> Derive these from `business.json` (competitor names + your `industry` / `business_type` /
> space). Examples using placeholders:

- `"{Competitor Name}" {your space}`
- `"{Your Product}" {your space}`
- `"{your space}" {region} 2026`
- `"{your industry}" regulation 2026`

### Discovery queries (run every scan — Phase 2.5)
Broad, advertiser-agnostic queries that surface **new** entrants, not the known set.
Build them from `business.json` (industry / business_type / space):

- `new {your space} app {region} 2026 launch`
- `best {your space} apps {region} 2026` (comparison listicles reveal the current field)
- `{your space} startup {region} funding 2026`
- `{your industry} {business_type} app {region} 2026`
- `"{your space}" {region} Play Store new 2026`

## Per-Competitor Strategic Axis (for the report's strategic card)

For every Tier 1 competitor, the audit must surface four signals each week:

1. **Product update** — what shipped on Android + iOS this week (with version + What's New)
2. **Ads direction** — channels active (Google Ads / LinkedIn Ads / Meta Ads), creative themes, targeting hints
3. **Social direction** — Instagram (visual + reels) + LinkedIn (text + community) — content themes + cadence
4. **Actionable insight for your product** — concrete recommendation derived from this competitor's moves
