"""Refresh pipeline: run every 3 days (see .github/workflows/refresh.yml).
Picks the stalest companies first. Each source is a plug-in returning dicts."""
import os, psycopg
from sources import job_postings, news_signals

BATCH = int(os.environ.get("BATCH", 500))

def main():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT id,name,domain,careers_url FROM companies "
            "ORDER BY last_refreshed_at ASC NULLS FIRST LIMIT %s", (BATCH,)).fetchall()
        for cid, name, domain, careers in rows:
            for j in job_postings(name, domain, careers):
                conn.execute(
                    "INSERT INTO job_postings(company_id,title,location,url,department) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(url) DO UPDATE SET last_seen=now()",
                    (cid, j["title"], j.get("location"), j["url"], j.get("department")))
            for s in news_signals(name):
                conn.execute(
                    "INSERT INTO signals(company_id,kind,headline,url,published_at) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(url) DO NOTHING",
                    (cid, s["kind"], s["headline"], s["url"], s.get("published_at")))
            conn.execute("UPDATE companies SET last_refreshed_at=now() WHERE id=%s", (cid,))
            conn.commit()

if __name__ == "__main__":
    main()
