# GCC Intel portal (MVP scaffold)
- `db/schema.sql` – Postgres schema (companies, job_postings, signals, users)
- `workers/` – `seed.py` loads a CSV seed list; `refresh.py` re-researches the stalest companies (jobs + news); `sources.py` holds pluggable sources
- `web/` – Next.js: landing, login (stub), gated companies table, pricing
- `.github/workflows/refresh.yml` – runs refresh every 3 days

Run: `psql $DATABASE_URL -f db/schema.sql; python workers/seed.py seed.csv; cd web && npm i && npm run dev`

Not yet built: real auth, payments, Google Ads/Search Console setup, SEO company pages, licensed enrichment.
