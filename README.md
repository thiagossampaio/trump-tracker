<h1 align="center">Trump Tracker — Aberration Feed</h1>

<p align="center">
  <em>An AI pipeline that monitors, scores, and publishes unprecedented Trump presidency events —<br>fully autonomous, factual, and open source.</em>
</p>

<p align="center">
  <a href="https://github.com/features/actions"><img src="https://img.shields.io/github/actions/workflow/status/your-org/trump-tracker/pipeline.yml?branch=main&style=for-the-badge&label=pipeline" alt="Pipeline status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js 15">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Cloudflare-Workers-F38020?style=for-the-badge&logo=cloudflare&logoColor=white" alt="Cloudflare">
  <img src="https://img.shields.io/badge/Supabase-Postgres-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase">
  <img src="https://img.shields.io/badge/Claude-Sonnet-CC785C?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude Sonnet">
  <img src="https://img.shields.io/badge/Cost-~%241.30%2Fmo-brightgreen?style=for-the-badge" alt="~$1.30/month">
</p>

<p align="center">
  <a href="#live-demo">Live Demo</a> ·
  <a href="#how-it-works">Architecture</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#running-the-pipeline">Pipeline</a> ·
  <a href="#frontend-development">Frontend</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## What Is This

Trump Tracker is an **autonomous AI pipeline** that monitors news sources every 2 hours, uses Claude Sonnet to score each event's historical aberration on a 1–10 scale, and publishes a public feed of the most unprecedented moments of the Trump presidency.

Each event gets an **Aberration Score** — a factual, dimensioned measurement of how far an event deviates from historical U.S. presidential norms. A score of 1 means routine governance. A score of 10 means no precedent exists in American presidential history.

**This is not an opinion site.** There is no editorial slant, no satire, no commentary. The pipeline sources from Tier 1 outlets (AP, Reuters), classifies using structured criteria, and requires human review for scores ≥ 8 before anything is published. The system classifies — it does not judge.

The entire stack runs for **~$1.30/month**, with the Anthropic API as the only paid service.

---

## Live Demo

> 🌐 **[trumptracker.workers.dev](https://trumptracker.workers.dev)** — N aberrations since inauguration (Jan 20, 2025)

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                  GITHUB ACTIONS · cron every 2h                     │
│                                                                     │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌─────────┐│
│  │ingest_agent │──▶│classify_agent│──▶│dedup_agent │──▶│publish  ││
│  │             │   │              │   │            │   │_agent   ││
│  │ AP RSS      │   │ Claude Sonnet│   │ pgvector   │   │         ││
│  │ Reuters RSS │   │ score 1–10   │   │ cosine sim │   │ Supabase││
│  │ GDELT       │   │ PT-BR        │   │ dedup      │   │ events  ││
│  │ Guardian    │   │ headline +   │   │            │   │ + ISR   ││
│  │ NewsAPI     │   │ summary      │   │            │   │ trigger ││
│  └─────────────┘   └──────┬───────┘   └────────────┘   └─────────┘│
│                           │                                         │
│                      score ≥ 8?                                     │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │telegram_    │                                  │
│                    │agent        │──▶ Human approves/rejects        │
│                    └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────▼────────────┐
                   │   Cloudflare Pages    │
                   │   Next.js 15 + ISR    │
                   │                       │
                   │  /            feed    │
                   │  /event/[slug]  page  │
                   │  /api/og      images  │
                   └───────────────────────┘
```

### The 5 Agents

| Agent | Input | Output |
|-------|-------|--------|
| `ingest_agent.py` | AP, Reuters, GDELT, Guardian, NewsAPI, RSS | `raw_articles` with `status=pending` |
| `classify_agent.py` | pending articles | Aberration Score, PT-BR headline/summary, category |
| `dedup_agent.py` | classified articles | semantic dedup via pgvector cosine similarity |
| `publish_agent.py` | approved articles | public `events` table + ISR revalidation |
| `telegram_agent.py` | score ≥ 8 events | Telegram inline keyboard for human review |

---

## Aberration Score

The score is computed across 4 independent dimensions — not a single judgment.

| Dimension | Max | What it measures |
|-----------|:---:|------------------|
| **Historical Precedent** | 4 | Has this ever happened in U.S. presidential history? |
| **Velocity / Reversal** | 2 | How fast did the position change or reversal occur? |
| **Institutional Impact** | 2 | Effect on courts, financial markets, allies, or Congress |
| **System Reaction** | 2 | Judicial blocks, bipartisan outcry, diplomatic incident |

**Score bands:**

| Score | Label | Meaning |
|:-----:|-------|---------|
| 1–3 | Routine | Expected behavior within historical presidential norms |
| 4–5 | Notable | Unusual but has some historical precedent |
| 6–7 | Significant | Rare; meaningful deviation from norms |
| 8–9 | Historic | No clear precedent in modern American presidency |
| 10 | Unprecedented | No parallel exists in U.S. presidential history |

---

## Features

| Feature | Description |
|---------|-------------|
| **Autonomous pipeline** | GitHub Actions cron every 2h — zero manual operation |
| **AI scoring** | Claude Sonnet classifies with structured 4-dimension rubric |
| **Semantic dedup** | pgvector cosine similarity prevents duplicate events |
| **Human-in-the-loop** | Telegram review required for score ≥ 8 before publishing |
| **Infinite scroll feed** | Reverse-chronological, cursor-paginated, ISR-cached |
| **Individual event pages** | `/event/[slug]` with score breakdown and share button |
| **Dynamic OG images** | `/api/og?slug=...` — every event shareable on Twitter/WhatsApp |
| **Historical backfill** | Retrieve events from Jan 20, 2025 with adaptive source strategy |
| **ISR revalidation** | `/api/revalidate` flushes `events-feed` cache on new publishes |
| **~$1.30/month** | Only Claude API is paid; everything else is free tier |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- A [Supabase](https://supabase.com) project (free tier)
- An [Anthropic](https://console.anthropic.com) API key (Claude Sonnet)
- An [OpenAI](https://platform.openai.com) API key (embeddings)
- Optional: [NewsAPI](https://newsapi.org), [The Guardian](https://open-platform.theguardian.com), [Telegram bot](https://core.telegram.org/bots)

### 1. Clone and install

```bash
git clone https://github.com/your-org/trump-tracker.git
cd trump-tracker

# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd web && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys (see Environment Variables section below)
```

### 3. Configure sources

```bash
cp config/sources.example.yml config/sources.yml
# Optionally add/remove RSS feeds or search queries
```

### 4. Initialize the database

Run the following files in your [Supabase SQL Editor](https://app.supabase.com), in order:

```sql
-- 1. Create tables, indexes, and the public_feed view
\i supabase/schema.sql

-- 2. Seed anchor events from inauguration day (calibrates AI scoring)
\i supabase/seed_anchor_events.sql
```

---

## Running the Pipeline

The pipeline is designed to run sequentially. Each agent reads from and writes to Supabase — no intermediate files.

```bash
# Step 1 — Fetch articles from the last 2 hours
python agents/ingest_agent.py

# Step 2 — AI classification (Aberration Score + PT-BR headline)
python agents/classify_agent.py

# Step 3 — Semantic deduplication via pgvector
python agents/dedup_agent.py

# Step 4 — Publish approved events to the public feed
python agents/publish_agent.py

# Optional: dry-run any step without writing to the database
python agents/ingest_agent.py --dry-run
python agents/classify_agent.py --dry-run --limit 5
```

### Historical Backfill

To retroactively process events since inauguration:

```bash
# Dry run first — validate volume and estimated API cost
python agents/backfill_agent.py --from 2025-01-20 --to 2025-02-20 --dry-run

# Run for real (processes 1 day at a time)
python agents/backfill_agent.py --from 2025-01-20

# For periods > 365 days, use a conservative dedup threshold
python agents/dedup_agent.py --dedup-threshold 0.95
```

**Backfill source strategy by period:**

| Period | Strategy | Sources used |
|--------|----------|--------------|
| ≤ 60 days | `short` | NewsAPI + GDELT + Guardian + RSS |
| ≤ 365 days | `medium` | GDELT + Guardian + RSS |
| > 365 days | `long` | GDELT + Guardian + Wikipedia |

### Telegram Moderation

Events with score ≥ 8 are held until a human approves or rejects them via Telegram:

```bash
python agents/telegram_agent.py   # send pending high-score events for review
```

Alternatively, deploy the Cloudflare webhook worker in `cloudflare/` to handle approvals inline from the Telegram message.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|----------|:--------:|-------------|
| `SUPABASE_URL` | ✅ | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase service role key (not anon) |
| `ANTHROPIC_API_KEY` | ✅ | Claude Sonnet for AI classification |
| `OPENAI_API_KEY` | ✅ | text-embedding-3-small for semantic dedup |
| `NEWSAPI_KEY` | ⚪ | newsapi.org free developer key |
| `GUARDIAN_API_KEY` | ⚪ | open-platform.theguardian.com free key |
| `TELEGRAM_BOT_TOKEN` | ⚪ | Required for human-in-the-loop moderation |
| `TELEGRAM_CHAT_ID` | ⚪ | Your Telegram chat/group ID for moderation |
| `NEXT_PUBLIC_SITE_URL` | ⚪ | Production URL for OG image meta tags |
| `REVALIDATE_SECRET` | ⚪ | Bearer token for `/api/revalidate` endpoint |

> ⚪ = optional for local development; required for full production pipeline.

---

## Frontend Development

```bash
cd web
npm run dev      # Start dev server at http://localhost:3000
npm run build    # Build for production
npm run deploy   # Build (OpenNext) + deploy to Cloudflare Workers
npm run preview  # Local Cloudflare Workers preview
```

### Cloudflare Deployment

Set secrets before deploying:

```bash
cd web
wrangler secret put SUPABASE_URL
wrangler secret put SUPABASE_KEY
wrangler secret put REVALIDATE_SECRET
wrangler secret put NEXT_PUBLIC_SITE_URL   # e.g. https://trumptracker.workers.dev
```

Then deploy:

```bash
npm run deploy
```

The frontend is a Next.js 15 App Router app deployed via [`@opennextjs/cloudflare`](https://github.com/opennextjs/opennextjs-cloudflare). Pages are ISR-cached and invalidated via `POST /api/revalidate` when new events are published.

---

## GitHub Actions Setup

The pipeline runs automatically every 2 hours via GitHub Actions. To enable it:

1. Fork or push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add all required secrets from the [Environment Variables](#environment-variables) table
4. The workflow at `.github/workflows/pipeline.yml` activates automatically

To trigger a historical backfill manually:

1. Go to **Actions → Backfill → Run workflow**
2. Enter `--from` and `--to` date range

---

## Project Structure

```
trump-tracker/
├── agents/
│   ├── ingest_agent.py       # Fetch articles from 5+ sources
│   ├── classify_agent.py     # Claude Sonnet scoring + PT-BR translation
│   ├── dedup_agent.py        # pgvector semantic deduplication
│   ├── publish_agent.py      # Publish events + trigger ISR revalidation
│   ├── telegram_agent.py     # Human-in-the-loop review via Telegram
│   └── backfill_agent.py     # Historical retroactive processing
│
├── web/                      # Next.js 15 frontend (Cloudflare Pages)
│   ├── app/
│   │   ├── page.tsx          # Infinite scroll feed (RSC)
│   │   ├── event/[slug]/     # Individual event page
│   │   └── api/
│   │       ├── events/       # Cursor-paginated events API
│   │       ├── og/           # Dynamic OG image generation
│   │       └── revalidate/   # ISR cache invalidation
│   ├── components/
│   │   ├── EventCard.tsx
│   │   ├── AberrationBadge.tsx
│   │   ├── ScoreBreakdown.tsx
│   │   ├── ShareButton.tsx
│   │   ├── CategoryFilter.tsx
│   │   └── InfiniteScroll.tsx
│   └── lib/
│       ├── supabase.ts       # Singleton client
│       └── events.ts         # Type definitions
│
├── supabase/
│   ├── schema.sql            # Tables, indexes, pgvector, public_feed view
│   └── seed_anchor_events.sql # 5 inauguration-day anchor events
│
├── cloudflare/               # Telegram webhook Worker
│   └── wrangler.toml
│
├── config/
│   ├── sources.example.yml   # Template for news source config
│   └── sources.yml           # Your active config (gitignored)
│
├── .github/
│   └── workflows/
│       ├── pipeline.yml      # Cron: every 2h (ingest → classify → dedup → publish)
│       └── backfill.yml      # Manual: workflow_dispatch
│
├── .env.example              # Environment variable template
├── requirements.txt          # Python dependencies
└── README.md
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | Next.js 15 App Router + TailwindCSS + shadcn/ui | ISR native, edge-compatible, Cloudflare Pages deploy |
| **Hosting** | Cloudflare Workers (via OpenNext) | Global CDN, free tier, zero cold starts |
| **Database** | Supabase — Postgres + pgvector | Native vector similarity, robust free tier, Row Level Security |
| **AI — Classification** | Claude Sonnet (Anthropic) | Superior historical reasoning vs. GPT-4o; Prompt Caching cuts cost |
| **AI — Embeddings** | `text-embedding-3-small` (OpenAI) | Best cost/quality for semantic dedup (1536 dims, $0.00002/1k tokens) |
| **Orchestration** | GitHub Actions (cron) | Free for public repos, 2000 min/month, native secrets |
| **Moderation** | Telegram Bot API + Cloudflare Worker | Mobile-first, zero infra, inline keyboards, zero compute cost |
| **Primary sources** | AP RSS, Reuters RSS | Tier 1, no API key, maximum reliability |
| **Secondary sources** | GDELT, The Guardian, NewsAPI | GDELT is free and unlimited; Guardian/NewsAPI have generous free tiers |

### Estimated Monthly Cost

| Service | Cost |
|---------|------|
| Cloudflare Pages / Workers | $0 |
| Supabase (free tier — 500 MB, 50k req/day) | $0 |
| GitHub Actions (public repo) | $0 |
| AP RSS + Reuters RSS | $0 |
| GDELT API | $0 |
| Guardian API (free developer key) | $0 |
| NewsAPI (free: 100 req/day) | $0 |
| Claude API (~20 useful events/day × $0.002) | ~$1.20 |
| OpenAI Embeddings (~20 embeddings/day) | ~$0.10 |
| **Total** | **~$1.30/month** |

---

## Editorial Principles

Trump Tracker is an **archive**, not a platform.

- **This system classifies — it does not editorialize.** Headlines describe what happened, not what it means.
- **The Aberration Score measures historical deviation from U.S. presidential norms** — not political approval or disapproval. A norm-breaking left-wing action would score the same as a right-wing one.
- **Human review is mandatory for score ≥ 8.** No high-impact event is published without a human approving it via Telegram.
- **Every published event links to at least one Tier 1 or Tier 2 verified source.** No anonymous or unverifiable sourcing.

---

## Contributing

PRs are welcome. Please open an issue before starting large changes so we can align on approach.

```bash
# Fork → clone → create a feature branch
git checkout -b feat/your-feature

# Make changes, test locally
python agents/ingest_agent.py --dry-run

# Submit PR against main
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for coding conventions, agent architecture guidelines, and the review process.

---

## Disclaimer

**Trump Tracker is a factual archive, not a political platform.**

1. **Non-partisan:** This tool applies the same historical deviation methodology regardless of political affiliation. An unprecedented action by any president would score the same.
2. **Source-verified:** All published events link to Tier 1 (AP, Reuters, C-SPAN) or Tier 2 (Guardian, major wire services) sources. No anonymous sourcing.
3. **AI limitations:** Claude Sonnet may misclassify events. Human review is required for scores ≥ 8. Classification errors can be reported via GitHub Issues.
4. **No affiliation:** This project has no affiliation with any political party, campaign, PAC, or advocacy organization.
5. **Data ownership:** No user data is collected. The only external services are Supabase (your own project) and the AI APIs listed above.

---

## License

MIT © 2025 Trump Tracker contributors

---

## Star History

<a href="https://www.star-history.com/#your-org/trump-tracker&timeline">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=your-org/trump-tracker&type=timeline&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=your-org/trump-tracker&type=timeline" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=your-org/trump-tracker&type=timeline" />
  </picture>
</a>

---

<p align="center">
  Built with Claude Code · Powered by Claude Sonnet · Hosted on Cloudflare
</p>
