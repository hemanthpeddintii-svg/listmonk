"""Import a seed CSV (name,domain,parent_company,hq_country,cities,industry,careers_url).
Build the seed from public lists (GCC Journal, AIM, Nasscom-Zinnov) after checking each site's terms.
Usage: python seed.py gcc_seed.csv"""
import csv, os, sys, psycopg

with psycopg.connect(os.environ["DATABASE_URL"]) as conn, open(sys.argv[1]) as f:
    for r in csv.DictReader(f):
        conn.execute(
            """INSERT INTO companies(name,domain,parent_company,hq_country,india_cities,industry,careers_url,source)
               VALUES(%s,%s,%s,%s,%s,%s,%s,'seed') ON CONFLICT(domain) DO NOTHING""",
            (r["name"], r["domain"], r.get("parent_company"), r.get("hq_country"),
             [c.strip() for c in r.get("cities", "").split(";") if c.strip()],
             r.get("industry"), r.get("careers_url")))
