"""Topic news ingestion -> articles (+ auto-detected expansions). Run with refresh.py every 3 days.
Stores headline, source, link and date ONLY (no full text) — readers click through to the publisher."""
import os, re, sys, urllib.parse, xml.etree.ElementTree as ET, email.utils, requests, psycopg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relevance import is_relevant   # headline must be about GCCs in India (drops Gulf / Greater Chennai Corp / unrelated items)

CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi NCR", "Gurugram", "Noida", "Kolkata", "Ahmedabad", "Coimbatore", "Kochi"]
TOPICS = ['"global capability center" India', '"GCC" India "capability centre"', "GCC India new centre opens",
          "GCC India hiring"] + [f'"capability center" {c}' for c in CITIES]
OPEN = re.compile(r"\b(open|opens|opened|launch|launches|inaugurat\w+|set[s]? up|establish\w*|expand\w*|new (gcc|centre|center)|to hire)\b", re.I)
CLOSE = re.compile(r"\b(shut|shuts|closes|closing|wind[s]? down|layoffs?)\b", re.I)
GULF = re.compile(r"gulf cooperation|saudi|uae|qatar|kuwait|oman|bahrain", re.I)   # skip Gulf Cooperation Council items

def fetch(topic):
    r = requests.get("https://news.google.com/rss/search?q=" + urllib.parse.quote(topic) + "&hl=en-IN&gl=IN&ceid=IN:en", timeout=20)
    for it in ET.fromstring(r.content).iter("item"):
        src = it.find("source")
        yield dict(title=it.findtext("title"), url=it.findtext("link"), source=src.text if src is not None else None,
                   at=email.utils.parsedate_to_datetime(it.findtext("pubDate")) if it.findtext("pubDate") else None)

def main():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        names = conn.execute("SELECT id,name,parent_company FROM companies").fetchall()
        run = conn.execute("INSERT INTO ingestion_runs(kind) VALUES('news') RETURNING id").fetchone()[0]; n = 0
        for topic in TOPICS:
            try: items = list(fetch(topic))
            except Exception: continue
            for a in items:
                if GULF.search(a["title"] or "") or not is_relevant(a["title"]): continue
                city = next((c for c in CITIES if c.lower() in a["title"].lower()), None)
                cid = next((i for i, nm, par in names if (par and par.lower() in a["title"].lower())), None)
                new = conn.execute(
                    "INSERT INTO articles(kind,title,source_name,source_url,city,company_id,published_at) VALUES('news',%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(source_url) DO NOTHING RETURNING id", (a["title"], a["source"], a["url"], city, cid, a["at"])).fetchone()
                if new:
                    n += 1
                    if OPEN.search(a["title"]) and "gcc" in a["title"].lower() + " capability":
                        ev = "closed" if CLOSE.search(a["title"]) else "opened" if re.search(r"open|launch|inaugur|set", a["title"], re.I) else "expanded"
                        conn.execute("INSERT INTO expansions(company_id,company_name,city,event,summary,source_url,announced_at) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_url) DO NOTHING",
                                     (cid, a["title"][:90], city, ev, a["title"], a["url"], a["at"]))
            conn.commit()
        conn.execute("UPDATE ingestion_runs SET finished_at=now(), rows_ok=%s, rows_in=%s WHERE id=%s", (n, n, run)); conn.commit()
        print("new articles:", n)

if __name__ == "__main__": main()
