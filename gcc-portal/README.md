# GCC Intel portal

Next.js + Postgres + Python workers.

## Features
- Landing page with live stats + email capture, pricing, SEO (sitemap/robots/meta)
- Real auth: email+password (bcrypt), signed JWT cookie, middleware gate, admin role (`ADMIN_EMAILS`)
- Plans (free/pro/team) enforced in `web/lib/plans.js`: row limits, job/signal history, CSV export, alerts, saved items
- Company explorer (search, city/industry filters, newest-refreshed first), company detail pages, save/star
- Dashboard (saved companies, alerts), Admin (stats, CSV import, plan management, ingestion runs)
- Billing webhook `/api/billing/webhook` (HMAC-signed; map Razorpay/Stripe payloads to it)
- `workers/`: `seed.py` + `refresh.py` (jobs + news, stalest first) on a 3-day schedule

## Media hub (v3)
- `/news` (newest first, filter by city/type), `/expansions` tracker grouped by year+quarter, `/reports/[year]/[q1-4]` auto-built from data, `/jobs`, `/cities/[city]` hubs, `/learn` (GCC vs Gulf Cooperation Council explainer + FAQ schema)
- `workers/news.py`: pulls topic headlines (headline + source + link only, no full text) and auto-detects unverified expansions; admin can verify, publish original articles, add expansions

## Run
```
export DATABASE_URL=postgresql://user:pass@localhost/gcc JWT_SECRET=$(openssl rand -hex 32)
export ADMIN_EMAILS=you@company.com BILLING_WEBHOOK_SECRET=... SITE_URL=https://yourdomain
psql $DATABASE_URL -f db/schema.sql
cd web && npm i && npm run build && npm start
```
Load data later: log in as admin -> /admin -> upload CSV (see `seed_sample.csv`), or `python workers/seed.py file.csv`.

## Not done
Razorpay/Stripe checkout + provider payload mapping, email delivery (alerts, password reset), rate limiting, more job sources.
