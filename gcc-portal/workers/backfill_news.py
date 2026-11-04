"""One-off backfill of `articles` (+ auto-detected `expansions`) from Google News RSS using date windows.
Stores headline, source, link, date, city and a coarse sector tag ONLY. Never fetches article bodies.

Usage: DATABASE_URL=... python workers/backfill_news.py [--start 2026-05-04] [--end 2026-11-05] [--sleep 1.0]
Reuses the regexes/city list from news.py.
"""
import os, re, sys, time, argparse, concurrent.futures as cf, datetime as dt, urllib.parse, xml.etree.ElementTree as ET, email.utils
import requests, psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from news import CITIES as BASE_CITIES, OPEN, CLOSE, GULF  # noqa: E402
from relevance import is_relevant  # noqa: E402

CITIES = BASE_CITIES + ["Jaipur", "Indore", "Visakhapatnam"]
CITY_ALIASES = {"Gurgaon": "Gurugram", "Bangalore": "Bengaluru", "Vizag": "Visakhapatnam", "Cochin": "Kochi",
                "Bombay": "Mumbai", "Calcutta": "Kolkata", "Madras": "Chennai"}

# generic topics: ~2-week windows; narrower topics (cities / sectors): ~4-week windows
GENERIC = ['"global capability center" India', '"GCC" India', '"global capability centre" India',
           "GCC India hiring", "GCC India leadership appointed", "GCC India AI centre", "GCC India new centre opens"]
NARROW = ([f'"capability centre" {c}' for c in ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Gurugram", "Noida",
                                               "Kolkata", "Ahmedabad", "Coimbatore", "Kochi", "Jaipur", "Indore", "Vizag"]]
          + ["GCC BFSI India", "GCC pharma India", "GCC semiconductor India", "GCC retail India", "GCC automotive India",
             "GCC policy India state government", "GCC Tier-2 cities"])

SECTORS = [  # (tag, regex) -- first-match semantics not used; all matching tags are added
    ("BFSI", r"\b(bfsi|bank\w*|insurance|insurer|fintech|financial services|capital markets|asset management|wealth|payments?|lender|nbfc)\b"),
    ("Pharma", r"\b(pharma\w*|biotech|life ?sciences?|healthcare|medical|drug|clinical)\b"),
    ("Retail", r"\b(retail\w*|e-?commerce|consumer goods|cpg|fmcg|supermarket)\b"),
    ("Auto", r"\b(auto|automotive|automaker|vehicles?|ev|mobility|car maker)\b"),
    ("Semiconductor", r"\b(semiconductors?|chips?|chipmaker|vlsi|silicon)\b"),
    ("AI", r"\b(ai|a\.i\.|gen ?ai|generative|artificial intelligence|machine learning|agentic|llm)\b"),
    ("Policy", r"\b(policy|government|govt|state cabinet|minister|incentives?|mou|gcc policy|scheme|budget)\b"),
]
SECTORS = [(t, re.compile(r, re.I)) for t, r in SECTORS]


def windows(start, end, days):
    d = start
    while d < end:
        e = min(d + dt.timedelta(days=days), end)
        yield d, e
        d = e


def fetch(topic, a, b):
    q = f"{topic} after:{a:%Y-%m-%d} before:{b:%Y-%m-%d}"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-IN&gl=IN&ceid=IN:en"
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (gcc-portal backfill)"})
            if r.status_code == 200:
                out = []
                for it in ET.fromstring(r.content).iter("item"):
                    src = it.find("source")
                    pd = it.findtext("pubDate")
                    title = (it.findtext("title") or "").strip()
                    source = src.text.strip() if src is not None and src.text else None
                    if source and title.endswith(" - " + source):  # drop the "- Publisher" suffix Google appends
                        title = title[: -len(source) - 3].strip()
                    out.append(dict(title=title, url=it.findtext("link"), source=source,
                                    at=email.utils.parsedate_to_datetime(pd) if pd else None))
                return out
            last = f"HTTP {r.status_code}"
        except Exception as e:  # network/parse errors: retry then give up
            last = repr(e)
        time.sleep(3 * (attempt + 1))
    print(f"  ! failed ({last}): {q}", flush=True)
    return []


def detect_city(title):
    t = title.lower()
    for c in CITIES:
        if c.lower() in t:
            return c
    for alias, c in CITY_ALIASES.items():
        if re.search(r"\b" + alias.lower() + r"\b", t):
            return c
    return None


def sector_tags(title):
    return [t for t, rx in SECTORS if rx.search(title)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-05-04")
    ap.add_argument("--end", default="2026-11-05")  # `before:` is exclusive, so 11-05 includes 11-04
    ap.add_argument("--sleep", type=float, default=1.0, help="sleep after each request, per worker")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    lo = dt.datetime.combine(start, dt.time.min, dt.timezone.utc)
    hi = dt.datetime.combine(end, dt.time.min, dt.timezone.utc)

    jobs = [(t, a, b) for t in GENERIC for a, b in windows(start, end, 14)] + \
           [(t, a, b) for t in NARROW for a, b in windows(start, end, 28)]
    print(f"{len(jobs)} requests planned", flush=True)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        names = conn.execute("SELECT id,name,parent_company FROM companies").fetchall()
        run = conn.execute("INSERT INTO ingestion_runs(kind, note) VALUES('news_backfill', %s) RETURNING id",
                           (f"{start}..{end}",)).fetchone()[0]
        conn.commit()
        seen, n_art, n_exp, n_seen = set(), 0, 0, 0
        def work(job):
            items = fetch(*job)
            time.sleep(args.sleep)  # each worker pauses after every request
            return job, items

        pool = cf.ThreadPoolExecutor(max_workers=args.workers)
        for i, (job, items) in enumerate(pool.map(work, jobs), 1):
            topic, a, b = job
            added = 0
            for it in items:
                if not it["title"] or not it["url"] or not it["at"] or it["url"] in seen:
                    continue
                seen.add(it["url"]); n_seen += 1
                if GULF.search(it["title"]) or not is_relevant(it["title"]) or not (lo <= it["at"] < hi):
                    continue
                title = it["title"]
                city = detect_city(title)
                cid = next((cid for cid, nm, par in names if par and par.lower() in title.lower()), None)
                tags = sector_tags(title)
                new = conn.execute(
                    "INSERT INTO articles(kind,title,source_name,source_url,city,company_id,tags,published_at) "
                    "VALUES('news',%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_url) DO NOTHING RETURNING id",
                    (title, it["source"], it["url"], city, cid, tags, it["at"])).fetchone()
                if not new:
                    continue
                n_art += 1; added += 1
                tl = title.lower()
                if OPEN.search(title) and ("gcc" in tl or re.search(r"capability cent(er|re)", tl)):
                    ev = "closed" if CLOSE.search(title) else "opened" if re.search(r"\b(open|launch|inaugur|set[s]? up)", title, re.I) else "expanded"
                    r = conn.execute(
                        "INSERT INTO expansions(company_id,company_name,city,event,summary,source_url,announced_at) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_url) DO NOTHING RETURNING id",
                        (cid, title[:90], city, ev, title, it["url"], it["at"])).fetchone()
                    n_exp += 1 if r else 0
            conn.commit()
            print(f"[{i}/{len(jobs)}] {a}..{b} {topic[:40]:40s} items={len(items)} new={added}", flush=True)
        conn.execute("UPDATE ingestion_runs SET finished_at=now(), rows_in=%s, rows_ok=%s WHERE id=%s", (n_seen, n_art, run))
        conn.commit()
        print(f"done: unique items seen={n_seen}, new articles={n_art}, new expansions={n_exp}", flush=True)


if __name__ == "__main__":
    main()
