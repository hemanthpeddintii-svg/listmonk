"""State GCC policy tracker: loads workers/data/policies.json into `policies` (upsert on state+name).

Every row in the JSON was written from a page that was fetched and read; `source_url` is mandatory and a row without
one is refused. Re-run after editing the JSON:  DATABASE_URL=... python workers/policy_tracker.py
Rows in the table that are no longer in the JSON are left untouched unless --prune is given.
"""
import os, sys, json, argparse, psycopg

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "policies.json")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--prune", action="store_true")
    args = ap.parse_args()
    rows = json.load(open(PATH))["policies"]
    bad = [r for r in rows if not r.get("source_url") or not r.get("state") or not r.get("name")]
    if bad:
        sys.exit(f"refusing to load: {len(bad)} rows lack state/name/source_url")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO policies(state,name,year,summary,incentives,source_url,status,source_type,extra_sources,fetched_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT(state,name) DO UPDATE SET year=EXCLUDED.year, "
                "summary=EXCLUDED.summary, incentives=EXCLUDED.incentives, source_url=EXCLUDED.source_url, status=EXCLUDED.status, "
                "source_type=EXCLUDED.source_type, extra_sources=EXCLUDED.extra_sources, fetched_at=now()",
                (r["state"], r["name"], r.get("year"), r.get("summary"), r.get("incentives") or [], r["source_url"],
                 r.get("status"), r.get("source_type"), r.get("extra_sources") or []))
        if args.prune:
            conn.execute("DELETE FROM policies WHERE (state,name) NOT IN (SELECT * FROM unnest(%s::text[], %s::text[]))",
                         ([r["state"] for r in rows], [r["name"] for r in rows]))
        conn.commit()
    print(f"policies loaded: {len(rows)}")


if __name__ == "__main__":
    main()
