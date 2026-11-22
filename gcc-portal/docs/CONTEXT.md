# Context (read this first when you pick the project up)

Snapshot as of 2026-11-22. Things marked **(untested)** were written but never run for real.

## Where things are
- Repo: `github.com/hemanthpeddintii-svg/listmonk` (a fork of listmonk; the portal is a **separate app inside a subfolder**, `gcc-portal/`; listmonk's own code is untouched).
- Branch: `claude/gcc-companies-portal-arqoke`. Open pull request: #1 into `master`.
- Extra files outside `gcc-portal/`: `/render.yaml` (Render blueprint) and `/.github/workflows/gcc-portal-*.yml` (CI and scheduled jobs; GitHub only reads workflows from the repo root).
- Nothing is deployed anywhere yet. It has only run inside a temporary cloud session.

## Stack
Next.js 14 (app router, plain JavaScript, no TypeScript) + Postgres + Python 3 workers. No ORM: SQL in `web/lib/*.js` through `pg`. Auth is our own: bcrypt password + signed JWT cookie (`jose`). Styling is one hand-written CSS file (`web/app/globals.css`) plus `community.css` and `profile.css`; no UI library, no Tailwind. Fonts are system stacks (Iowan Old Style/Palatino for headlines). The hero map is a canvas drawn in code (`web/components/IndiaMap.js`).

## Folder map (inside `gcc-portal/`)
- `web/` the website. `app/` pages and server actions, `components/`, `lib/` (db, auth, plans, stats, content, community, ratelimit, mail), `scripts/` (migrate, seed-demo, load-seed, entrypoint).
- `workers/` Python jobs (see below). `workers/data/` caches, catalogues and the removed-articles backup.
- `db/schema.sql` the whole schema, idempotent (re-runnable). `db/seed_data.sql.gz` starter dataset.
- `deploy/aws-setup.sh`, `Dockerfile`, `Dockerfile.worker`, `docker-compose.yml`, `.env.example`, `DEPLOY.md`, `HOSTING-FREE.md`, `run-test.sh`.
- `docs/` this folder.

## Data model (Postgres)
`companies` (+Wikidata profile fields), `articles` (news; `category`, `city`, `company_id`, `relevant`, `score`, `comment_count`), `expansions`, `people_moves`, `fundings`, `job_postings`, `policies`, `events`, `digests`, `subscribers`, `users` (plan, role), `comments`, `votes`, `follows`, `saved_companies`, `saved_searches`, `payments`, `leads`, `rate_limits`, `ingestion_runs`.

## Plans and access (single source of truth: `web/lib/plans.js`)
Free: 25 companies visible, 3 latest jobs per company, top-3 rankings in reports, no export, 10 saved companies, no alerts. Pro/Team: full list, long history, CSV export, alerts. **BILLING_MODE=test** shows a plan switcher on the dashboard (instant plan change, no payment) and a banner; set `live` when payments exist. An admin is anyone whose signup email is in `ADMIN_EMAILS`.

## What is built
Public: home (masthead, live data map, three doors, front page), news (filters, top), story pages (on-site; link out to the publisher) with comments, upvotes and follows, expansion tracker, people moves, deals, state-policy tracker, events, quarterly reports (from May 2026), city hubs, jobs, company profiles, search, methodology, learn, The GCC Weekly archive, RSS. Accounts: stepped signup/login, saved companies, follows and a personal feed, Pro alerts and CSV export, subscribe with double opt-in. Admin: stats, publish articles, add or verify expansions, CSV import, set plans, subscribers, ingestion runs. Security: DB-backed rate limits, CSP and other headers, JWT secret guard in production, HMAC-signed billing webhook (`/api/billing/webhook`).

## Workers (all free sources)
- News: `news.py`, `backfill_news.py` (Google News RSS windows), `sources_rss.py` (about 90 working outlet feeds), all filtered through `relevance.py`.
- Cleanup and structure: `classify.py` (categories), `link_articles.py` (headline to company), `extract_trackers.py` (people moves, deals).
- Companies: `import_public.py` (385 parents from public knowledge), `enrich_wikidata.py` (370 of 395 matched by official website; description, logo, employees, founded, ticker).
- Jobs: `ats_jobs.py` (public Greenhouse, Lever, Ashby, SmartRecruiters boards only). Covers **24 of 395** companies.
- Policies and events: `policy_tracker.py`, `events.py` (each row has a source URL that was actually read).
- Digest and schedule: `digest.py` (26 weekly issues backfilled), `scheduler.py` + `crontab` (IST: news daily 06:00, refresh Sunday 02:30, digest Monday 07:00), `run_weekly.sh`.

## Data in the starter set (`db/seed_data.sql.gz`, loaded on first boot when `SEED_DATA=1`)
395 companies, 1,439 stories (May 2026 onward, all categorised, 375 linked to companies), 203 expansions, 33 people moves, 3 deals (all ANSR), 1,333 jobs, 17 state policies, 12 events, 26 digests. Users, comments, votes, follows and subscribers are **not** in the seed; they live only in whatever database runs the site.

## Environment variables
`DATABASE_URL`, `JWT_SECRET` (required in production), `ADMIN_EMAILS`, `SITE_URL`, `BILLING_MODE` (test|live), `BILLING_WEBHOOK_SECRET`, `SEED_DATA`, `SMTP_*` (email; unset means nothing is sent), `POSTGRES_*`, `DOMAIN`. See `.env.example`. **Secrets are never committed.**

## Testing locally
`./run-test.sh` (needs Postgres) builds, seeds demo users and serves on :3111. Demo logins, password `demo12345`: `admin@gccintel.test`, `pro@gccintel.test`, `free@gccintel.test`. Demo users exist only in test builds; the Render/AWS deployments create none.

## Known issues and honest limits
- **Payments not built.** The webhook exists; checkout does not.
- **Email is off** until SMTP is configured (the code was tested against local test servers only).
- **Jobs coverage is thin.** Big banks and tech parents use Workday/Taleo (no free API). Bosch alone is 484 of 1,333 rows.
- **Expansions and people moves are auto-detected** and labelled "Detected". The same event covered by several outlets can show several times (for example AssetMark, Blackstone).
- **Deals tracker is almost empty** (3 rows). The home page "ecosystem deals" door can show 0.
- **Company coverage is from public knowledge**, not an authoritative registry. Cities and "GCC function" are estimates. There is no India headcount and no contacts (those need paid data).
- **Docker images and the Render blueprint have never been built for real** (no Docker in the cloud session) **(untested)**. `deploy/aws-setup.sh` is only syntax-checked **(untested)**. The standalone build and boot script were run.
- Most article links are Google News redirect URLs.
- Jobs dates are the job board's posted/updated date, so recent months look heavier than the past.

## Lessons from building it (so they are not repeated)
- Parallel builds: always `NEXT_DIST=.next-<name> npx next build`; a plain build while a server runs on `.next` breaks that server. Kill a dev server by port (`fuser -k 3111/tcp`), not by process name.
- A Python script that leaves a Postgres transaction open (`idle in transaction`) while calling an API will block an `ALTER TABLE` and freeze every page that reads that table. Use `autocommit=True` and short connections. `scripts/migrate.mjs` uses lock timeouts and retries for this reason.
- `pg_dump` output clears `search_path` for its session; reset it (`SET search_path TO public`) before running more queries.
- Quality bar from QA: headlines must actually be about GCCs in India (the word GCC also means Greater Chennai Corporation and the Gulf Cooperation Council). `relevance.py` is the gate; keep it on every ingestion path.
- Design feedback: avoid heavy shadow cards everywhere and repeated italic-orange accents; keep emoji out; keep copy specific.

## Decisions already made
Stack above; freemium; company-level data only; headline-and-link news; no paid data tools; news daily with weekly deep refresh (the early "every 3 days" idea was dropped); a fresh repo was requested originally but the portal lives in a subfolder of this fork because that is the repo the session could push to.
