<div align="center">

# 🚀 AI-PM Operator

### The AI operating system for product managers — run your product, growth & ops from inside Claude Code.

**Stop prompting. Start operating.** 19 production-grade PM skills that connect to your *real* tools — Jira, Confluence, Google Analytics, Search Console, the app stores — and actually do the work: audit the board, score the backlog, draft the PRD, write the leadership deck, track competitors, surface what customers are asking for.

[![Free trial](https://img.shields.io/badge/Free-7--day%20trial-22c55e)](https://dydb.in)
[![Skills](https://img.shields.io/badge/Skills-19-5C4EE5)](#-the-skills)
[![Built for](https://img.shields.io/badge/Built%20for-Claude%20Code-5C4EE5)](https://claude.com/claude-code)
[![Works with](https://img.shields.io/badge/Works%20with-Jira%20·%20Confluence%20·%20GA4-0052CC)](#-what-it-connects-to)
[![License](https://img.shields.io/badge/License-Commercial-blue)](#-license)

[**Get started →**](https://dydb.in) · [How it works](#-how-it-works) · [The skills](#-the-skills) · [Why not just prompts?](#-why-skills-beat-prompts)

</div>

---

## 🎯 What is this?

**AI-PM Operator** is a Claude Code project you drop into your repo (or a new folder). On first launch it **sets itself up for your business** — infers what you're building, asks a few questions, and tailors every skill to your company, metrics, and competitors.

Then it runs the parts of a PM's job that don't need you:

> *"Audit my Jira board, score the backlog, draft a PRD for this feature, write the Monday leadership deck, tell me what changed with my competitors, and show me what customers are asking for."* — all real commands, all producing leadership-ready output.

Built by a Head of Product who runs two companies on it. Every workflow is production-tested, not a prompt template.

---

## ⚡ Quick start

```bash
# 1. Drop AI-PM Operator into your project (or a fresh folder) and open Claude Code
claude

# 2. It detects a fresh install and sets itself up for your business.
#    Just say:  set up      (or run /operator-onboarding)

# 3. Run your first workflow:
#    /briefing        → your morning digest: what needs you today
#    /prioritize      → RICE/ICE-score your backlog, what to build next
#    /prd-generator   → turn an idea into a complete spec (and Jira tickets)
```

**7 days free, then $49.** [Start the trial →](https://dydb.in)

---

## 📦 The skills

19 skills, grouped by the job you're doing. Each reads your business profile so the output speaks your company's language.

### ☀️ Daily & delivery
| Skill | What it does |
|---|---|
| `/briefing` | Morning digest — board health + what's on your plate + metric moves + competitor deltas, led by the top 3 things that need you today |
| `/scrum-master` | Audits your Jira board, finds stale/blocked/unassigned issues, nudges owners |
| `/weekly-plan` | Capacity-aware sprint planning, carries over work, sets priorities |
| `/jira-vs-code` | Flags spec ↔ code drift before you ship |

### 🧭 Decide & spec
| Skill | What it does |
|---|---|
| `/prioritize` | General **RICE / ICE** backlog scoring — ranks the backlog, recommends next |
| `/prd-generator` | Turns a raw idea into a complete PRD (Gherkin ACs, telemetry, edge cases) → optional Jira Epic + Stories |
| `/idea-generator` | Captures repeated workflows into reusable skills |

### 📊 Analytics & reporting
| Skill | What it does |
|---|---|
| `/monthly-board-prep` | Leadership-deck MoM report, metrics driven by *your* revenue model |
| `/weekly-metrics` | GA4 traffic & behavior report with anomaly detection |
| `/ppa` | Flow-Framework delivery metrics with week-over-week trends |
| `/play-console` | Play Store ASO: installs, CVR, keywords, vitals, experiments |
| `/search-console` | Google Search Console SEO health + keyword opportunities |

### 🔭 Market & customers
| Skill | What it does |
|---|---|
| `/competitor-tracker` | Weekly competitor pulse — releases, ratings, ads, hiring, deltas |
| `/voice-of-customer` | Aggregates reviews + search + support into ranked themes, drafts tickets |
| `/release-notes` | Leadership/release deck of what shipped, with measured impact |

### 💰 Monetization & setup
| Skill | What it does |
|---|---|
| `/audit-offers` | Offer/discount/promo ROI audit — kill/keep/consolidate |
| `/operator-onboarding` | Self-setup: tailors everything to your business |
| `/help` | "What can you do for me?" — recommends a starter set for your business |

---

## 🔌 What it connects to

Real tools, real data — not best-guesses:

**Jira** · **Confluence** · **Google Analytics 4** · **Google Search Console** · **Google Play Console** · **Slack** (alerts) · your **production database** (read-only).

Configure once in `.env`; every credential stays **local to your machine**.

---

## 🧠 How it works

1. **`business.json`** — a profile of your company (type, industry, metrics, competitors, stack) that the onboarding builds for you. Every skill reads it, so nothing is generic.
2. **Skills** — markdown playbooks Claude executes against your real tools.
3. **Self-improving** — it records your corrections and gets sharper over time.

Nothing is hardcoded to any industry. A **B2B SaaS**, a **consumer app**, a **marketplace**, and an **e-commerce** PM each get a toolkit shaped to their business.

---

## 💡 Why skills beat prompts

| One-off prompt | AI-PM Operator skill |
|---|---|
| You re-explain context every time | Reads your `business.json` automatically |
| Different output each run | Consistent, structured, leadership-ready |
| Lives in your head | A shared command your whole team can run |
| Talks *about* the work | Connects to Jira/GA/stores and *does* the work |

---

## 🌟 What makes it different

- **Production-connected** — pulls from your actual Jira, analytics, and app stores.
- **Business-aware** — adapts to your metrics and revenue model via `business.json`.
- **End-to-end** — discovery → prioritization → spec → delivery → reporting → competitive intel.
- **Built by an operator** — running real companies, not a content kit.
- **Self-hosted & private** — your credentials never leave your machine.

---

## 💸 Pricing

**7-day free trial, then $49.** One purchase, all 19 skills + updates.

[**Start free → dydb.in**](https://dydb.in)

---

## ❓ FAQ

**Do I need to be technical?** No — onboarding is a conversation. If you can use Claude Code, you can run it.

**Where does my data go?** Credentials and team data stay on your machine. (A small, non-sensitive business summary — business type/industry — is sent to the maker for product analytics; opt out with `OPERATOR_TELEMETRY=off`.)

**Jira or Linear?** Jira today; Linear is on the [roadmap](https://dydb.in).

**Can my whole team use it?** Yes — share the setup; each PM runs it in their own Claude Code.

---

## 📜 License

Commercial software. © AI-PM Operator. A 7-day free trial is included; continued use requires a license from [dydb.in](https://dydb.in). Not open-source; please don't redistribute the skills.

## 📞 Questions?

[Get it →](https://dydb.in) · [LinkedIn](https://www.linkedin.com/in/mohitkhandelwaliitm/)

<div align="center">

**Stop prompting. Start operating.** → [dydb.in](https://dydb.in)

</div>
