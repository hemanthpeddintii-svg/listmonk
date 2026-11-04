"""India job postings from free public ATS JSON APIs (no auth, no scraping).

Supported: Greenhouse, Lever (US+EU), Ashby, SmartRecruiters, Workable.
For each company we try slug candidates derived from domain/parent/company name,
cache which (ats, slug) pairs exist in workers/data/ats_slugs.json, keep only
India-located postings from the last ~6 months, and upsert into job_postings.

Usage:  DATABASE_URL=... python workers/ats_jobs.py [--workers 16] [--budget 900]
                                                      [--recheck] [--limit N]
Library: fetch_company(name, domain, careers_url) -> list[dict]  (used by sources.py)
"""
import argparse, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

CACHE_PATH = Path(__file__).parent / "data" / "ats_slugs.json"
WINDOW_DAYS = 183
UA = {"User-Agent": "gcc-portal-jobs/1.0 (public ATS job-board reader)"}
TIMEOUT = (4, 15)
NEG_TTL_DAYS = 30           # re-probe companies with no ATS hit after this many days

INDIA_RE = re.compile(
    r"\b(india|bengaluru|bangalore|hyderabad|pune|chennai|mumbai|gurugram|gurgaon|noida|"
    r"delhi|kolkata|ahmedabad|coimbatore|kochi|cochin|jaipur|indore|visakhapatnam|vizag)\b", re.I)

_cache_lock = threading.Lock()
_tls = threading.local()
_host_gate = {}     # per-host semaphores for politeness
_gate_lock = threading.Lock()
HOST_LIMIT = {"apply.workable.com": 1}  # Workable rate-limits (Cloudflare 1015) aggressively


def _session():
    s = getattr(_tls, "s", None)
    if s is None:
        s = _tls.s = requests.Session()
        s.headers.update(UA)
    return s


def _gate(host):
    with _gate_lock:
        return _host_gate.setdefault(host, threading.BoundedSemaphore(HOST_LIMIT.get(host, 8)))


def _get(url, params=None):
    """GET json; returns (status, data|None). Retries once on 429/5xx."""
    host = url.split("/")[2]
    for attempt in range(2):
        try:
            with _gate(host):
                r = _session().get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == 0:
                    time.sleep(1.5 + 2 * attempt)
                    continue
                return r.status_code, None
            if r.status_code != 200:
                return r.status_code, None
            try:
                return 200, r.json()
            except ValueError:
                return 200, None
        except requests.RequestException:
            if attempt == 1:
                return 0, None
            time.sleep(0.5)
    return 0, None


def is_india(*texts):
    return any(t and INDIA_RE.search(t) for t in texts)


def _parse_dt(v):
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------- slugs
_SUFFIX = re.compile(
    r"\b(inc|incorporated|ltd|limited|llc|plc|corp|corporation|company|co|group|holdings|"
    r"technologies|technology|india|gds|global|bancorp|ag|se|sa|nv|gmbh)\b\.?", re.I)


def _norm(s):
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def slug_candidates(name, domain, parent=None):
    out = []

    def add(s):
        s = s.strip("-")
        if len(s) >= 3 and s not in out:
            out.append(s)

    label = (domain or "").lower().split(".")[0] if domain else ""
    if label and label not in ("www",):
        add(label)
    for src in (parent, re.sub(r"\bindia\b", "", name or "", flags=re.I)):
        n = _norm(src)
        if not n:
            continue
        for v in (n, _SUFFIX.sub("", n)):
            v = re.sub(r"\s+", " ", v).strip()
            if v:
                add(v.replace(" ", ""))
                add(v.replace(" ", "-"))
    return out[:6]


# ---------------------------------------------------------------- ATS adapters
# each returns (found: bool, postings: list[dict]) ; posting keys:
# title, location, url, department, first_seen(datetime)

def greenhouse(slug):
    st, d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", {"content": "false"})
    if st != 200 or not isinstance(d, dict) or "jobs" not in d:
        return False, []
    jobs = []
    for j in d["jobs"]:
        loc = (j.get("location") or {}).get("name")
        dt = _parse_dt(j.get("first_published")) or _parse_dt(j.get("updated_at"))
        jobs.append(dict(title=j.get("title"), location=loc, url=j.get("absolute_url"),
                         department=None, first_seen=dt))
    return True, jobs


def _lever(host, slug):
    st, d = _get(f"https://{host}/v0/postings/{slug}", {"mode": "json"})
    if st != 200 or not isinstance(d, list):
        return False, []
    jobs = []
    for j in d:
        c = j.get("categories") or {}
        locs = [c.get("location")] + list(c.get("allLocations") or [])
        loc = "; ".join(dict.fromkeys(x for x in locs if x))
        jobs.append(dict(title=j.get("text"), location=loc or None, url=j.get("hostedUrl"),
                         department=c.get("department") or c.get("team"),
                         first_seen=_parse_dt(j.get("createdAt"))))
    return True, jobs


def lever(slug):
    return _lever("api.lever.co", slug)


def lever_eu(slug):
    return _lever("api.eu.lever.co", slug)


def ashby(slug):
    st, d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if st != 200 or not isinstance(d, dict) or "jobs" not in d:
        return False, []
    jobs = []
    for j in d["jobs"]:
        if j.get("isListed") is False:
            continue
        locs = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
        pa = (j.get("address") or {}).get("postalAddress") or {}
        loc = "; ".join(dict.fromkeys(x for x in locs if x))
        if pa.get("addressCountry") and not loc:
            loc = pa["addressCountry"]
        jobs.append(dict(title=j.get("title"), location=loc or None, url=j.get("jobUrl"),
                         department=j.get("department") or j.get("team"),
                         first_seen=_parse_dt(j.get("publishedAt"))))
    return True, jobs


def smartrecruiters(slug):
    jobs, offset, found = [], 0, False
    while offset < 1000:
        st, d = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                     {"country": "in", "limit": 100, "offset": offset})
        if st != 200 or not isinstance(d, dict):
            return False, []
        total = d.get("totalFound", 0)
        if total == 0:
            return False, []
        found = True
        for j in d.get("content", []):
            l = j.get("location") or {}
            loc = l.get("fullLocation") or ", ".join(x for x in (l.get("city"), l.get("region"), (l.get("country") or "").upper()) if x)
            if (l.get("country") or "").lower() == "in" and "india" not in loc.lower():
                loc += ", India"
            jobs.append(dict(title=j.get("name"), location=loc,
                             url=f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                             department=(j.get("department") or {}).get("label"),
                             first_seen=_parse_dt(j.get("releasedDate"))))
        offset += 100
        if offset >= total:
            break
    return found, jobs


def workable(slug):
    st, d = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", {"details": "false"})
    if st != 200 or not isinstance(d, dict) or not d.get("jobs"):
        return False, []     # widget answers 200 + empty list for unknown accounts
    jobs = []
    for j in d["jobs"]:
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        jobs.append(dict(title=j.get("title"), location=loc or None, url=j.get("url"),
                         department=j.get("department"),
                         first_seen=_parse_dt(j.get("published_on") or j.get("created_at"))))
    return True, jobs


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "lever_eu": lever_eu, "ashby": ashby,
            "smartrecruiters": smartrecruiters, "workable": workable}
BOARD_URL = {
    "greenhouse": "https://boards.greenhouse.io/{s}", "lever": "https://jobs.lever.co/{s}",
    "lever_eu": "https://jobs.eu.lever.co/{s}", "ashby": "https://jobs.ashbyhq.com/{s}",
    "smartrecruiters": "https://careers.smartrecruiters.com/{s}",
    "workable": "https://apply.workable.com/{s}",
}


# ---------------------------------------------------------------- cache
def load_cache():
    try:
        return json.loads(CACHE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _cache_lock:
        data = json.dumps(cache, indent=1, sort_keys=True)
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(data)
    tmp.replace(CACHE_PATH)


def _filter(jobs, cutoff):
    keep = []
    for j in jobs:
        if not j.get("url") or not j.get("title"):
            continue
        if not is_india(j.get("location")):
            continue
        if not j.get("first_seen") or j["first_seen"] < cutoff:
            continue
        keep.append(j)
    return keep


def fetch_company(name, domain, careers_url=None, parent=None, cache=None, recheck=False):
    """Returns (hits, postings). hits=[{ats,slug,board_url,total,india}]; postings are
    India + last-6-months only, each tagged with 'ats'."""
    cache = cache if cache is not None else load_cache()
    key = (domain or name).lower()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    entry = cache.get(key)
    hits, postings = [], []

    def run(ats, slug):
        found, jobs = ADAPTERS[ats](slug)
        if not found:
            return None
        kept = _filter(jobs, cutoff)
        for j in kept:
            j["ats"] = ats
        hits.append(dict(ats=ats, slug=slug, board_url=BOARD_URL[ats].format(s=slug),
                         total=len(jobs), india=len(kept)))
        postings.extend(kept)
        return True

    if entry and entry.get("hits") is not None and not recheck:
        for h in entry["hits"]:
            run(h["ats"], h["slug"])
        return hits, postings
    if entry and not entry.get("hits") and not recheck:
        age = now - datetime.fromisoformat(entry["checked"])
        if age < timedelta(days=NEG_TTL_DAYS):
            return hits, postings

    for ats in ADAPTERS:
        for slug in slug_candidates(name, domain, parent):
            if run(ats, slug):
                break          # first slug that works for this ATS
    with _cache_lock:
        cache[key] = dict(name=name, checked=now.isoformat(timespec="seconds"),
                          hits=[{k: h[k] for k in ("ats", "slug", "board_url")} for h in hits])
    return hits, postings


# ---------------------------------------------------------------- main
def main():
    import psycopg
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--budget", type=int, default=900, help="seconds of runtime")
    ap.add_argument("--recheck", action="store_true", help="ignore cached negatives/slugs")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    conn = psycopg.connect(os.environ["DATABASE_URL"])
    rows = conn.execute("SELECT id,name,domain,parent_company,careers_url FROM companies ORDER BY id").fetchall()
    if a.limit:
        rows = rows[:a.limit]
    cache = load_cache()
    t0 = time.time()
    stats = dict(done=0, matched=0, inserted=0, skipped=0)
    by_ats = {}

    def work(row):
        cid, name, domain, parent, careers = row
        if time.time() - t0 > a.budget:
            return row, None, None
        try:
            return (row,) + fetch_company(name, domain, careers, parent, cache, a.recheck)
        except Exception as e:  # never kill the pool
            print(f"ERR {name}: {e!r}", file=sys.stderr)
            return row, None, None

    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(work, r) for r in rows]
        for n, f in enumerate(as_completed(futs), 1):
            (cid, name, domain, parent, careers), hits, postings = f.result()
            if hits is None:
                stats["skipped"] += 1
                continue
            stats["done"] += 1
            if hits:
                stats["matched"] += 1
                for h in hits:
                    by_ats[h["ats"]] = by_ats.get(h["ats"], 0) + 1
                print(f"[{n}/{len(rows)}] {name} ({domain}): " +
                      ", ".join(f"{h['ats']}/{h['slug']} {h['india']}/{h['total']}" for h in hits), flush=True)
            for j in postings:
                conn.execute(
                    "INSERT INTO job_postings(company_id,title,location,url,department,first_seen,last_seen) "
                    "VALUES(%s,%s,%s,%s,%s,%s,now()) "
                    "ON CONFLICT(url) DO UPDATE SET last_seen=now()",
                    (cid, j["title"][:500], j.get("location"), j["url"], j.get("department"), j["first_seen"]))
                stats["inserted"] += 1
            conn.execute("UPDATE companies SET last_refreshed_at=now() WHERE id=%s", (cid,)) if hits else None
            if hits and not (careers or "").strip():
                conn.execute("UPDATE companies SET careers_url=%s WHERE id=%s AND coalesce(careers_url,'')=''",
                             (hits[0]["board_url"], cid))
            conn.commit()
            if n % 25 == 0:
                save_cache(cache)
    save_cache(cache)
    conn.close()
    print(json.dumps(dict(stats, by_ats=by_ats, seconds=round(time.time() - t0))))


if __name__ == "__main__":
    main()
