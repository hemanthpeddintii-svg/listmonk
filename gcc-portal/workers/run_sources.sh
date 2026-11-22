#!/usr/bin/env bash
# Daily outlet-feed ingestion (idempotent). Usage:
#   workers/run_sources.sh               # live RSS/Atom feeds + last 10 days of site-scoped Google News for feed-less outlets
#   workers/run_sources.sh --backfill    # also walk 2026-05-04..today in 14-day windows per outlet (~45 min)
#   workers/run_sources.sh --check       # re-verify every feed URL and rewrite data/outlets.json (no inserts)
# Extra flags are passed through to sources_rss.py (e.g. --dry-run, --start 2026-08-01).
set -euo pipefail
cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-postgresql://gcc:gcc@localhost/gcc}"
exec python3 workers/sources_rss.py "$@"
