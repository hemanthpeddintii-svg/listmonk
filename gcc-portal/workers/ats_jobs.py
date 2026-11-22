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
DENY_PATH = Path(__file__).parent / "data" / "ats_slug_deny.json"   # {"domain": ["ats/slug", ...]} false positives
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


# ---------------------------------------------------------------- normalisation
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

CITY_ALIAS = {   # alias (lowercase, ascii) -> canonical display name
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru", "bengalooru": "Bengaluru",
    "bangalore urban": "Bengaluru", "bengaluru urban": "Bengaluru", "blr": "Bengaluru",
    "gurgaon": "Gurugram", "gurugram": "Gurugram",
    "bombay": "Mumbai", "mumbai": "Mumbai", "navi mumbai": "Navi Mumbai", "thane": "Thane",
    "madras": "Chennai", "chennai": "Chennai",
    "calcutta": "Kolkata", "kolkata": "Kolkata",
    "new delhi": "Delhi", "delhi": "Delhi", "delhi ncr": "Delhi", "ncr": "Delhi",
    "hyderabad": "Hyderabad", "secunderabad": "Hyderabad",
    "pune": "Pune", "noida": "Noida", "greater noida": "Noida", "ahmedabad": "Ahmedabad",
    "coimbatore": "Coimbatore", "kochi": "Kochi", "cochin": "Kochi", "jaipur": "Jaipur",
    "indore": "Indore", "visakhapatnam": "Visakhapatnam", "vizag": "Visakhapatnam",
    "trivandrum": "Thiruvananthapuram", "thiruvananthapuram": "Thiruvananthapuram",
    "mysore": "Mysuru", "mysuru": "Mysuru", "baroda": "Vadodara", "vadodara": "Vadodara",
    "chandigarh": "Chandigarh", "mohali": "Mohali", "nagpur": "Nagpur", "lucknow": "Lucknow",
    "bhubaneswar": "Bhubaneswar", "mangalore": "Mangaluru", "mangaluru": "Mangaluru",
}
MAJOR = {"Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Gurugram", "Noida", "Delhi",
         "Kolkata", "Ahmedabad", "Coimbatore", "Kochi", "Jaipur", "Indore", "Visakhapatnam"}
STATES = {
    "ka": "Karnataka", "karnataka": "Karnataka", "mh": "Maharashtra", "maharashtra": "Maharashtra",
    "tn": "Tamil Nadu", "tamil nadu": "Tamil Nadu", "tamilnadu": "Tamil Nadu",
    "ts": "Telangana", "tg": "Telangana", "telangana": "Telangana", "telengana": "Telangana",
    "ap": "Andhra Pradesh", "andhra pradesh": "Andhra Pradesh", "gj": "Gujarat", "gujarat": "Gujarat",
    "dl": "Delhi", "hr": "Haryana", "haryana": "Haryana", "up": "Uttar Pradesh",
    "uttar pradesh": "Uttar Pradesh", "rj": "Rajasthan", "rajasthan": "Rajasthan",
    "mp": "Madhya Pradesh", "madhya pradesh": "Madhya Pradesh", "wb": "West Bengal",
    "west bengal": "West Bengal", "pb": "Punjab", "punjab": "Punjab", "kl": "Kerala", "kerala": "Kerala",
    "ga": "Goa", "goa": "Goa", "br": "Bihar", "bihar": "Bihar", "jh": "Jharkhand", "jharkhand": "Jharkhand",
    "od": "Odisha", "or": "Odisha", "odisha": "Odisha", "ch": "Chandigarh", "hp": "Himachal Pradesh",
    "uk": "Uttarakhand", "uttarakhand": "Uttarakhand", "cg": "Chhattisgarh", "chhattisgarh": "Chhattisgarh",
}
_COUNTRY_TOK = {"india", "ind", "in", "asia", "apac", "emea", "asean", "south asia", "republic of india"}
_SITE_CODE = re.compile(r"^(mso|sez|it park|campus|office|hq|remote|hybrid|onsite)$", re.I)


def _ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _norm_loc_part(part):
    """One location (no ';') -> 'City, India' | 'City, State' | 'State, India' | 'Remote, India' | None."""
    raw = _ascii(part).strip()
    remote = bool(re.search(r"\bremote\b", raw, re.I))
    raw = re.sub(r"^\s*in\s*-\s*", "", raw, flags=re.I)          # 'IN-Pune' / 'IN-Bangalore-MSO'
    toks = [t for t in re.split(r"[,/|]|\s+-\s+|(?<=\w)-(?=\w{3,})", raw) if t and t.strip()]
    toks = [re.sub(r"\(.*?\)", "", t).strip() for t in toks]
    toks = [t for t in toks if t and t.lower() not in _COUNTRY_TOK and not _SITE_CODE.match(t)]
    city = state = None
    for t in toks:                                   # prefer a known city anywhere in the part
        tl = re.sub(r"\s+", " ", t.lower())
        if tl in CITY_ALIAS and city is None:
            city = CITY_ALIAS[tl]
        elif tl in STATES and state is None:
            state = STATES[tl]
    if city is None:                                 # 'hosur road bangalore' -> word match
        for t in toks:
            for w in re.findall(r"[a-z]+(?: [a-z]+)?", t.lower()):
                if w in CITY_ALIAS:
                    city = CITY_ALIAS[w]; break
            if city: break
    if city is None:
        for t in toks:
            if t.lower() not in STATES:
                city = t.strip().title(); break
    if city is None:
        if state:
            return f"{state}, India"
        return "Remote, India" if remote else None
    if state is None and city in {"Delhi"}:
        state = None
    if city in MAJOR or city in CITY_ALIAS.values() or not state or state == city:
        return f"{city}, India"
    return f"{city}, {state}"


def normalize_location(loc):
    """'Bengaluru, INDIA, India; Pune, MAHARASHTRA, India' -> 'Bengaluru, India; Pune, India'."""
    if not loc:
        return None
    parts = []
    for p in re.split(r"\s*[;\n]\s*", loc):
        n = _norm_loc_part(p)
        if n and n not in parts:
            parts.append(n)
    return "; ".join(parts) or None


def normalize_title(t):
    return re.sub(r"\s+", " ", t or "").strip()


_TRACK = re.compile(r"^(utm_|gh_src|source|src|ref|lever-source|lever-origin)", re.I)


def normalize_url(u):
    """Drop fragment/trailing slash/tracking params so near-identical apply URLs collapse."""
    sp = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(sp.query, keep_blank_values=True) if not _TRACK.match(k)]
    return urlunsplit((sp.scheme, sp.netloc.lower(), sp.path.rstrip("/") or "/", urlencode(q), ""))


def job_key(j):
    return (normalize_title(j["title"]).lower(), (j.get("location") or "").lower())


def dedupe(jobs):
    """Collapse same title+location (a company often lists one role as several requisitions);
    keep the most recently posted."""
    best = {}
    for j in sorted(jobs, key=lambda x: x["first_seen"]):
        best[job_key(j)] = j
    return list(best.values())


def upsert_job(conn, cid, j):
    """Insert a posting unless the same URL or the same (company,title,location) exists;
    in either case refresh last_seen. Returns True when a new row was inserted."""
    cur = conn.execute("UPDATE job_postings SET last_seen=now() WHERE url=%s", (j["url"],))
    if cur.rowcount:
        return False
    cur = conn.execute(
        "INSERT INTO job_postings(company_id,title,location,url,department,first_seen,last_seen) "
        "VALUES(%s,%s,%s,%s,%s,COALESCE(%s,now()),now()) ON CONFLICT DO NOTHING",
        (cid, j["title"], j.get("location"), j["url"], j.get("department"), j.get("first_seen")))
    if cur.rowcount:
        return True
    conn.execute("UPDATE job_postings SET last_seen=now() WHERE company_id=%s AND lower(title)=lower(%s) "
                 "AND lower(coalesce(location,''))=lower(coalesce(%s,''))",
                 (cid, j["title"], j.get("location")))
    return False


def cleanup_existing(conn):
    """One-off/idempotent: normalise title/location/url of stored rows, delete duplicates
    (keep newest first_seen, then highest id), then add the unique guard index."""
    rows = conn.execute("SELECT id,company_id,title,location,url,first_seen FROM job_postings").fetchall()
    groups, n_upd = {}, 0
    for id_, cid, title, loc, url, fs in rows:
        nt, nl = normalize_title(title), normalize_location(loc) if loc else loc
        groups.setdefault((cid, nt.lower(), (nl or "").lower()), []).append((fs, id_, nt, nl, title, loc))
    dele = []
    for key, items in groups.items():
        items.sort(key=lambda x: (x[0], x[1]))
        for it in items[:-1]:
            dele.append(it[1])
    if dele:
        conn.execute("DELETE FROM job_postings WHERE id = ANY(%s)", (dele,))
    for items in groups.values():
        fs, id_, nt, nl, title, loc = items[-1]
        if nt != title or nl != loc:
            conn.execute("UPDATE job_postings SET title=%s, location=%s WHERE id=%s", (nt, nl, id_))
            n_upd += 1
    conn.execute("DROP INDEX IF EXISTS uq_jobs_company_title_loc")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_company_title_loc ON job_postings "
                 "(company_id, lower(title), lower(coalesce(location,'')))")
    conn.commit()
    return len(rows), len(dele), n_upd


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
        add(label.replace("-", ""))
    for src in (parent, re.sub(r"\bindia\b", "", name or "", flags=re.I)):
        n = _norm(src)
        if not n:
            continue
        for v in (n, _SUFFIX.sub("", n)):
            v = re.sub(r"\s+", " ", v).strip()
            if v:
                add(v.replace(" ", ""))
                add(v.replace(" ", "-"))
    if label:
        for suf in ("inc", "india", "group", "global", "careers"):
            add(label + suf)
    return out[:10]


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
        j["title"] = normalize_title(j["title"])
        j["location"] = normalize_location(j["location"]) or j["location"]
        j["url"] = normalize_url(j["url"]) if "gh_jid" not in j["url"] else j["url"]
        keep.append(j)
    return dedupe(keep)


def fetch_company(name, domain, careers_url=None, parent=None, cache=None, recheck=False):
    """Returns (hits, postings). hits=[{ats,slug,board_url,total,india}]; postings are
    India + last-6-months only, each tagged with 'ats'."""
    cache = cache if cache is not None else load_cache()
    key = (domain or name).lower()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    entry = cache.get(key)
    hits, postings = [], []

    try:
        deny = set(json.loads(DENY_PATH.read_text()).get(key, []))
    except (OSError, ValueError):
        deny = set()

    def run(ats, slug):
        if f"{ats}/{slug}" in deny:
            return None
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
    ap.add_argument("--cleanup", action="store_true", help="normalise + dedupe stored rows, add unique index, exit")
    a = ap.parse_args()

    conn = psycopg.connect(os.environ["DATABASE_URL"])
    if a.cleanup:
        print("rows, deleted, updated:", cleanup_existing(conn))
        return
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
                if upsert_job(conn, cid, j):
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
