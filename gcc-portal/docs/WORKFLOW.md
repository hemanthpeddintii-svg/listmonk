# Working from git only (no cloud session, no long-lived local copy)

Goal: the repo is the single source of truth. Pick it up anywhere, change it, push it back, then delete the machine.

## Pick it up
```
git clone https://github.com/hemanthpeddintii-svg/listmonk.git
cd listmonk && git checkout claude/gcc-companies-portal-arqoke     # or master after PR #1 is merged
cd gcc-portal
```
Needs: Node 20+, Python 3.12+, Postgres 16. Read `docs/CONTEXT.md`, then `docs/NEXT_STEPS.md`.

## Run it
```
createdb gcc            # or point DATABASE_URL at any empty Postgres
export DATABASE_URL=postgresql://localhost/gcc
./run-test.sh
```
`run-test.sh` applies `db/schema.sql`, loads the starter data if the database is empty (set `SEED_DATA=0` to skip), creates the demo users, builds and serves on :3111.
Workers: `pip install -r workers/requirements.txt` then run any script in `workers/` with `DATABASE_URL` set (for example `python workers/sources_rss.py`).

## Change it and put it back
```
git checkout -b my-change
# ...edit...
cd web && NEXT_DIST=.next-check npx next build     # must pass before pushing
git add -A && git commit -m "what and why" && git push -u origin my-change
```
Open a pull request into the main branch. Never commit `.env`, tokens, or `node_modules`.

## Refresh the starter data in git (only when you want the repo to ship newer data)
```
pg_dump "$DATABASE_URL" --data-only --column-inserts --rows-per-insert=200 \
  -t companies -t articles -t expansions -t job_postings -t signals -t policies -t events -t people_moves -t fundings -t digests \
  | grep -v '^\\restrict\|^\\unrestrict' | gzip -9 > db/seed_data.sql.gz
```
Do not include users, comments, votes, follows or subscribers.

## What is NOT in git (and must be handled before you delete anything)
- The **running database** of any deployment: real users, comments, votes, follows, subscribers, payments. Back it up (`pg_dump`) or keep the host.
- **Secrets** (JWT secret, SMTP, payment keys, tokens): store them in your password manager and the host's environment settings.
- The cloud session's scratch files (screenshots, test scripts, a pre-cleanup database dump). They are disposable; the useful ones are already in the repo.

## Retiring the cloud session and local copies: checklist
Do this only after every item is true.
1. `git status` is clean and `git log origin/<branch>..` shows nothing unpushed.
2. A **fresh clone** in an empty folder has `gcc-portal/db/seed_data.sql.gz`, `docs/`, `web/package-lock.json`, and `./run-test.sh` works there.
3. The deployed site (if any) is up and its database is backed up.
4. Secrets are saved somewhere other than the machine you are about to delete.
5. Then delete: the cloud session (archive or delete it in the Claude app), local clones, and any local Postgres data. Nothing else depends on them.
