# GCC Intel — the daily record of India's GCC boom

Inc42-style news + intelligence portal for Global Capability Centers in India. Next.js 14 + Postgres + Python workers.

## Free hosting
See `HOSTING-FREE.md` (Render blueprint at the repo root: `render.yaml`).

## Test it (no payment gateway)
```
./run-test.sh            # needs Postgres; sets BILLING_MODE=test, seeds demo users, serves :3111
```
Demo logins (password `demo12345`): `admin@gccintel.test` (admin) · `pro@gccintel.test` (Pro) · `free@gccintel.test` (Free).
In test mode the Dashboard has a plan switcher (free / pro / team) so you can try every tier instantly.

## What's in it
- **Public:** front page (masthead, live data map, three doors), news (filters, top), story pages with comments/votes/follows, expansion tracker, people moves, deals, state-policy tracker, events, quarterly reports (from May 2026), city hubs, jobs, company profiles (Wikidata-enriched), search, methodology, learn (GCC vs Gulf Cooperation Council), The GCC Weekly archive, RSS.
- **Accounts:** stepped signup/login, saved companies, follows + personal feed, alerts (Pro), CSV export (Pro), subscribe/unsubscribe with double opt-in.
- **Admin:** stats, publish articles, add/verify expansions, CSV import, plan management, subscribers, ingestion runs.
- **Workers (free sources only):** `news.py`/`sources_rss.py` (90 feeds + Google News), `ats_jobs.py` (Greenhouse/Lever/Ashby/SmartRecruiters), `enrich_wikidata.py`, `classify.py`, `link_articles.py`, `extract_trackers.py`, `digest.py`, `scheduler.py` (news daily, refresh weekly, digest Monday).
- **Deploy:** `DEPLOY.md`, `Dockerfile`, `docker-compose.yml`, `.env.example`, CI/cron workflows.

## Known limits
Payments not built (webhook endpoint exists, `BILLING_MODE=live` later). Email sending needs SMTP env vars. Jobs cover 24 companies (public ATS only; banks use Workday/Taleo). Expansions/people moves are auto-detected and marked until verified; several outlets covering one event can show it more than once.
