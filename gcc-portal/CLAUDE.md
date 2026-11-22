# Notes for Claude (and humans) working in gcc-portal/
Start with `docs/CONTEXT.md` (what exists, constraints, lessons), `docs/OBJECTIVE.md` (why), `docs/NEXT_STEPS.md` (what to do), `docs/WORKFLOW.md` (git-only workflow).
Rules: no paid data tools; company-level data only; headline + link only for news; never fabricate data; label auto-detected items; keep the editorial, non-template look.
Build with `NEXT_DIST=.next-<name> npx next build`; never leave a Postgres transaction open across network calls; every ingestion path must call `workers/relevance.py`.
