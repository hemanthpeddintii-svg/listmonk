#!/usr/bin/env bash
# One-command test run (no payment gateway). Needs Postgres running and DATABASE_URL set.
set -e
export DATABASE_URL=${DATABASE_URL:-postgresql://gcc:gcc@localhost/gcc}
export BILLING_MODE=test JWT_SECRET=${JWT_SECRET:-test-secret} ADMIN_EMAILS=admin@gccintel.test SITE_URL=${SITE_URL:-http://localhost:3111}
psql "$DATABASE_URL" -q -f db/schema.sql >/dev/null
cd web && npm i --silent && node scripts/seed-demo.mjs && npx next build >/dev/null && exec npx next start -p ${PORT:-3111}
