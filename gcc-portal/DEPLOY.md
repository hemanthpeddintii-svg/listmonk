# Deploying GCC Intel

Three moving parts: a **web** app (Next.js 14), a **Postgres 16** database, and a **worker** (Python jobs on a schedule).
The web app applies `db/schema.sql` itself at boot, so a fresh database needs no manual step.

| Job | When (IST) | What |
|---|---|---|
| `run_weekly.sh news` | daily 06:00 | headlines, outlet feeds, classify, link to companies |
| `run_weekly.sh refresh` | Sunday 02:30 | job postings, signals, ATS boards, Wikidata, policies, events |
| `run_weekly.sh digest` | Monday 07:00 | build **The GCC Weekly** for the week that just ended, email it if SMTP is set |

## 0. Before you start

1. **A domain** and the ability to edit its DNS.
2. **Secrets** (generate once, keep in a password manager):
   ```
   openssl rand -hex 32     # JWT_SECRET  (the server refuses to boot in production without it)
   openssl rand -hex 24     # POSTGRES_PASSWORD
   ```
3. **Email (optional but recommended).** Any SMTP account works: Brevo, Amazon SES (SMTP interface), Mailgun, Postmark, a Gmail app password for a trial. Without it the site works, digests are still built and archived, but nothing is mailed and `/subscribe` can only show confirm links in test mode.
   Set SPF and DKIM for the sending domain at your provider or digests will land in spam.
4. **Data.** A fresh database is empty. Either restore a dump of the current database (fastest, section 5) or load from scratch:
   ```
   python workers/import_public.py                        # 385 parent companies from public research
   python workers/sources_rss.py --backfill               # news since 2026-05-04 (about 45 min)
   ./workers/run_weekly.sh refresh                        # jobs, enrichment
   python workers/classify.py && python workers/link_articles.py
   python workers/digest.py --backfill 26                 # fills the /weekly archive
   ```

Environment variables are documented line by line in `.env.example`.

---

## A. One VPS with Docker Compose and Caddy (recommended)

Any 2 GB Ubuntu box works (Hetzner, DigitalOcean, Lightsail).

```bash
# 1. Docker
curl -fsSL https://get.docker.com | sh

# 2. Code
git clone <your repo url> && cd <repo>/gcc-portal      # the folder with docker-compose.yml

# 3. Config
cp .env.example .env
nano .env        # set at least: POSTGRES_PASSWORD, JWT_SECRET, SITE_URL=https://yourdomain, DOMAIN=yourdomain,
                 # ADMIN_EMAILS=you@yourdomain, and SMTP_* if you have them. Keep BILLING_MODE=test for now (section E).

# 4. DNS: create an A record  yourdomain -> the server IP, and open ports 80 and 443.

# 5. Start (db, web, worker, and Caddy for HTTPS)
docker compose --profile caddy up -d --build
docker compose ps                    # db, web, worker should become "healthy"
docker compose logs -f web           # first boot prints "migrate: applied N statements"
```

Caddy gets the certificate on the first request to `https://yourdomain` (give it a minute). Check:
`curl -I https://yourdomain/api/health` returns 200 and the `Content-Security-Policy` header.

**First admin.** Open `https://yourdomain/signup` and register with the exact email you put in `ADMIN_EMAILS`. That account is admin and `/admin` appears in the menu. (Already registered before setting the variable? `docker compose exec db psql -U gcc gcc -c "UPDATE users SET role='admin' WHERE email='you@yourdomain'"`.)

**Run a job by hand.** `docker compose exec worker ./run_weekly.sh news` (or `refresh`, `digest`). Next run times: `docker compose exec worker python scheduler.py --list`.

**Update.** `git pull && docker compose --profile caddy up -d --build`. The web container re-applies the schema on start; it is idempotent and uses a 5 s lock timeout per statement, so a long-running query cannot freeze the site.

**Without Caddy** (you already run nginx/Traefik): `docker compose up -d`, then proxy to `127.0.0.1:3000` and pass `X-Forwarded-For`. Rate limiting uses the first address in that header.

---

## B. Render, Railway or Fly.io with managed Postgres

Build context is the `gcc-portal` folder in every case.

| Service | Build | Notes |
|---|---|---|
| Postgres | the platform's managed add-on | copy its connection string into `DATABASE_URL` (add `?sslmode=require` if it needs TLS) |
| web | `Dockerfile` (its last stage is the web app) | port 3000, health check `/api/health`, applies the schema at boot |
| worker | `Dockerfile.worker` | no port; a "background worker" that runs `python scheduler.py` |

Environment for **web**: `DATABASE_URL`, `JWT_SECRET`, `SITE_URL`, `ADMIN_EMAILS`, `BILLING_MODE`, `BILLING_WEBHOOK_SECRET`, `SMTP_*`.
Environment for **worker**: `DATABASE_URL`, `SITE_URL`, `SMTP_*`.

- **Render:** create the Postgres instance, then a *Web Service* (runtime Docker, root directory `gcc-portal`, Dockerfile `./Dockerfile`, health check path `/api/health`) and a *Background Worker* (same root directory, Dockerfile `./Dockerfile.worker`). Put the database's *Internal* URL in `DATABASE_URL` for both.
- **Railway:** add the Postgres plugin, then two services from the repo with root directory `gcc-portal`; for the worker set `RAILWAY_DOCKERFILE_PATH=Dockerfile.worker`. Reference the database as `${{Postgres.DATABASE_URL}}`.
- **Fly.io:** from `gcc-portal`, `fly launch --dockerfile Dockerfile` for web (internal port 3000), `fly postgres create` (or use Neon) and `fly secrets set JWT_SECRET=... DATABASE_URL=...`. For the worker, a second app with `--dockerfile Dockerfile.worker` and no `[http_service]` section.
- Prefer one container? Skip the worker service and run the jobs from GitHub Actions (section C, step 4).

---

## C. Vercel for web, Neon or Supabase for Postgres, GitHub Actions for the workers

Cheapest setup, nothing to keep running.

1. **Database.** Create a Neon (or Supabase) project and copy the *pooled* connection string, add `?sslmode=require`.
2. **Schema.** Vercel does not run the migration at boot. Apply it once, and after every schema change:
   ```
   cd web && npm ci && DATABASE_URL='postgresql://...' node scripts/migrate.mjs
   ```
   or run the **migrate-db** workflow from the Actions tab.
3. **Web.** Import the repo in Vercel, set *Root Directory* to `gcc-portal/web`. Environment variables: `DATABASE_URL`, `JWT_SECRET`, `SITE_URL`, `ADMIN_EMAILS`, `BILLING_MODE`, `BILLING_WEBHOOK_SECRET`, `SMTP_*`. Add the domain under *Settings > Domains*. (`output: standalone` is only switched on by the Docker build; Vercel uses its own packaging.)
4. **Workers on GitHub Actions.** In the repo: *Settings > Secrets and variables > Actions*, add `DATABASE_URL`, `SITE_URL`, and `SMTP_URL` (or `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`) plus `SMTP_FROM`. Workflows:
   - `daily-news.yml` 06:00 IST, `weekly-refresh.yml` Sunday 02:30 IST, `weekly-digest.yml` Monday 07:00 IST, `ci.yml` on every push (build, migrate twice, boot check, docker build), `migrate.yml` manual.
   - **GitHub reads workflows only from the repository root.** This project currently sits inside the `listmonk` repo as `gcc-portal/`, so root-level copies named `.github/workflows/gcc-portal-*.yml` (they run with `working-directory: gcc-portal` and never touch listmonk's own workflows) are the ones that run. If `gcc-portal` becomes its own repo, delete the `gcc-portal-` copies; the files in `gcc-portal/.github/workflows/` then work as they are. Keep the two sets in sync when you edit.
   - Scheduled workflows are paused by GitHub after 60 days without repository activity; re-enable them from the Actions tab if that happens.
   - GitHub cron is best effort and can start 5 to 30 minutes late.

---

## D. Go-live checklist

- [ ] `JWT_SECRET` set to a fresh 64-hex value (the app exits at boot otherwise)
- [ ] `SITE_URL` is the final `https://` origin, no trailing slash (feeds, sitemap, confirm and unsubscribe links all use it)
- [ ] HTTPS works; `curl -I https://yourdomain` shows `Strict-Transport-Security` and `Content-Security-Policy`
- [ ] Session cookie is `Secure` (automatic in production; it only works over HTTPS)
- [ ] `ADMIN_EMAILS` set, you signed up, `/admin` opens; **demo accounts do not exist** on this database (they come from `web/scripts/seed-demo.mjs`, never run that in production)
- [ ] `BILLING_MODE=test` hides nothing and gives every visitor free plan switching: decide deliberately (section E)
- [ ] `curl -s -o /dev/null -w "%{http_code}" -X POST https://yourdomain/api/billing/webhook` returns **503** until `BILLING_WEBHOOK_SECRET` is set
- [ ] SMTP set; subscribe with your own address, receive the confirm email, confirm, then click unsubscribe in a test issue (`python workers/digest.py --week <monday> --to you@example.com`)
- [ ] SPF and DKIM pass for the sending domain (send to a mail-tester address)
- [ ] `/weekly` lists issues, `/weekly/latest` redirects, `/rss.xml` and `/weekly/rss.xml` validate (https://validator.w3.org/feed/)
- [ ] `/sitemap.xml` and `/robots.txt` load; submit the sitemap in Google Search Console
- [ ] Worker is alive: `docker compose logs worker` shows `scheduler: 3 jobs`, or the first Actions run is green
- [ ] Backup job in place (below) and one restore rehearsed
- [ ] Postgres is not reachable from the internet (compose does not publish it)

## Backup and restore

```bash
# nightly dump (cron on the VPS), keep 14 days
docker compose exec -T db pg_dump -U gcc -Fc gcc > /backups/gcc-$(date +%F).dump
find /backups -name 'gcc-*.dump' -mtime +14 -delete

# restore into an empty database
docker compose exec -T db pg_restore -U gcc -d gcc --clean --if-exists < /backups/gcc-2026-11-05.dump
```
Managed Postgres (Neon, Supabase, Render, Railway): turn on their point-in-time backups and still take a weekly `pg_dump` off-platform.
To move today's data to production: `pg_dump -Fc $LOCAL_DATABASE_URL > gcc.dump`, then `pg_restore --no-owner --clean --if-exists -d $PROD_DATABASE_URL gcc.dump`. Afterwards delete demo users: `DELETE FROM users WHERE email LIKE '%@gccintel.test';`

## E. Switching `BILLING_MODE` to live later

**The payment gateway is not built.** `BILLING_MODE=live` today only turns the test conveniences off: no yellow bar, no free plan switcher, so nobody can become Pro without an admin changing the plan in `/admin`. What exists: plan limits (`web/lib/plans.js`), the `payments` table, and `POST /api/billing/webhook`, which accepts

```
POST /api/billing/webhook          header  x-signature: hex( HMAC-SHA256(BILLING_WEBHOOK_SECRET, rawBody) )
{ "event_id": "...", "email": "buyer@x.com", "plan": "pro|team", "amount_minor": 99900, "currency": "INR", "status": "paid", "provider": "razorpay" }
```
It answers 503 while `BILLING_WEBHOOK_SECRET` is empty, 401 on a bad signature, and is idempotent on `event_id`.

To go live you still need to build: a checkout page (Razorpay Checkout or Stripe Checkout), a small adapter that verifies the provider's own signature and maps its payload to the shape above, and renewal/cancellation handling. Then: set `BILLING_WEBHOOK_SECRET`, set `BILLING_MODE=live`, redeploy, make one real payment with a small amount and confirm the user's plan and `plan_expires_at` change.

## Security notes

- Headers are set in `web/next.config.js`: CSP (inline scripts allowed because Next needs them; no third-party origins; images from https), `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, HSTS, `nosniff`.
- Login and signup: 10 attempts per 15 minutes per IP+email and 30 per 15 minutes per email (table `rate_limits`). Subscribe: 5 per hour per IP, 3 per hour per email, plus a honeypot field.
- Sessions: HS256 JWT in an `httpOnly`, `sameSite=lax`, `Secure` (production) cookie, 30 days.
- Subscriber emails are only ever shown to admins (`web/lib/subscribers.js`); confirm/unsubscribe tokens are 192-bit random.
