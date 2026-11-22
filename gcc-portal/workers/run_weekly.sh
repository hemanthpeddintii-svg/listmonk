#!/usr/bin/env bash
# One entry point for every scheduled job (used by cron in the worker container, GitHub Actions and by hand).
#   workers/run_weekly.sh news      daily  : headline ingestion + outlet feeds + classify + link to companies
#   workers/run_weekly.sh refresh   weekly : deep refresh (jobs, signals, ATS postings, Wikidata enrichment)
#   workers/run_weekly.sh digest    weekly : build The GCC Weekly for the last completed IST week and mail it if SMTP is set
#   workers/run_weekly.sh all       news + refresh + digest, in that order
# Every step runs even if an earlier one failed; the exit code is non-zero if any step failed.
set -uo pipefail
cd "$(dirname "$0")"
[ -f /etc/gcc-worker.env ] && { set -a; . /etc/gcc-worker.env; set +a; }   # optional: for system cron, which does not pass env through
: "${DATABASE_URL:?DATABASE_URL is required}"
PY="${PYTHON:-python3}"
fail=0
step() {                       # step <label> <command...>
  local label="$1"; shift
  echo "[$(date -u +%FT%TZ)] >> $label"
  if "$@"; then echo "[$(date -u +%FT%TZ)] ok $label"; else echo "[$(date -u +%FT%TZ)] FAILED $label (exit $?)" >&2; fail=1; fi
}
news()    {
  step news.py            "$PY" news.py
  step sources_rss.py     "$PY" sources_rss.py
  step classify.py        "$PY" classify.py
  step link_articles.py   "$PY" link_articles.py
}
refresh() {
  step refresh.py         "$PY" refresh.py
  step ats_jobs.py        "$PY" ats_jobs.py --budget "${ATS_BUDGET:-1500}"
  step enrich_wikidata.py "$PY" enrich_wikidata.py --limit "${ENRICH_LIMIT:-300}"
  step policy_tracker.py  "$PY" policy_tracker.py
  step events.py          "$PY" events.py
}
digest()  { step digest.py "$PY" digest.py; }

case "${1:-}" in
  news) news ;;
  refresh) refresh ;;
  digest) digest ;;
  all) news; refresh; digest ;;
  *) echo "usage: $0 news|refresh|digest|all" >&2; exit 2 ;;
esac
exit $fail
