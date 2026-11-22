"""Upsert data/companies_public.csv into companies (source='public_research').
Key: domain (UNIQUE) - one row per parent; domain is the parent's domain.
Existing rows (e.g. seed rows) keep their name/source and only get blank fields filled.
Usage: python import_public.py [data/companies_public.csv]"""
import csv, os, sys, psycopg

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "data", "companies_public.csv")
SQL = """
INSERT INTO companies(name,domain,parent_company,hq_country,india_cities,industry,gcc_function,careers_url,source,last_refreshed_at)
VALUES(%(name)s,lower(%(domain)s),%(parent)s,%(hq)s,%(cities)s,%(industry)s,%(func)s,%(careers)s,'public_research',now())
ON CONFLICT(domain) DO UPDATE SET
  parent_company = COALESCE(NULLIF(companies.parent_company,''), EXCLUDED.parent_company),
  hq_country     = COALESCE(NULLIF(companies.hq_country,''),     EXCLUDED.hq_country),
  india_cities   = CASE WHEN COALESCE(array_length(companies.india_cities,1),0)=0 THEN EXCLUDED.india_cities ELSE companies.india_cities END,
  industry       = COALESCE(NULLIF(companies.industry,''),       EXCLUDED.industry),
  gcc_function   = COALESCE(NULLIF(companies.gcc_function,''),   EXCLUDED.gcc_function),
  careers_url    = COALESCE(NULLIF(companies.careers_url,''),    EXCLUDED.careers_url)
RETURNING (xmax = 0) AS inserted"""
n_new = n_upd = 0
with psycopg.connect(os.environ["DATABASE_URL"]) as conn, open(path, newline="") as f:
    for r in csv.DictReader(f):
        g = lambda k: (r.get(k) or "").strip() or None
        row = conn.execute(SQL, dict(
            name=r["name"].strip(), domain=r["domain"].strip(), parent=g("parent_company"), hq=g("hq_country"),
            cities=[c.strip() for c in (r.get("cities") or "").split(";") if c.strip()],
            industry=g("industry"), func=g("gcc_function"), careers=g("careers_url"))).fetchone()
        n_new += row[0]; n_upd += not row[0]
print(f"inserted={n_new} updated_existing={n_upd}")
