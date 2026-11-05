"""Enrich companies from Wikidata + Wikipedia (free public APIs, polite + resumable).

For every row in `companies` we resolve the PARENT company (parent_company, falling back to name):
  1. wbsearchentities for the parent name -> up to 6 candidate QIDs
  2. wbgetentities (batched) -> label, description, aliases, P856 website, P1128 employees, P571 founded,
     P414/P249 ticker, P154 logo, enwiki sitelink
  3. accept ONLY confident matches:
       - "domain": candidate's official website (P856) has the same registrable domain as companies.domain
                   AND the names overlap (guards against shared corporate sites)
       - "label" : normalised candidate label == normalised parent name, candidate has an English Wikipedia
                   article AND company-like claims (website/employees/ticker/industry/HQ), and is not a person
     Anything else stays blank. No guessing.
  4. Wikipedia intro extract (first 2 sentences, <=320 chars) via action=query&prop=extracts.

Cache: workers/data/wikidata_cache.json (search results, trimmed entities, extracts) -> re-runs are cheap and resumable.
Report: workers/data/wikidata_report.json (per-company match method / QID) + match rate printed.

Run: DATABASE_URL=... python workers/enrich_wikidata.py [--refresh] [--limit N] [--dry]
"""
import json, os, re, sys, time, argparse, urllib.parse, unicodedata
import requests, psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "wikidata_cache.json")
REPORT = os.path.join(HERE, "data", "wikidata_report.json")
API = "https://www.wikidata.org/w/api.php"
WPAPI = "https://en.wikipedia.org/w/api.php"
UA = "gcc-portal-enrich/1.0 (GCC India news portal; contact admin@gccintel.test) python-requests"
GAP = 1.1  # seconds between calls
S = requests.Session(); S.headers["User-Agent"] = UA
_last = [0.0]

STOP = {"inc", "corp", "corporation", "plc", "ag", "se", "sa", "nv", "group", "holdings", "holding", "company", "co", "ltd", "limited",
        "the", "llc", "lp", "us", "usa", "of", "and", "technologies", "technology", "global", "international"}
NOT_COMPANY_P31 = {"Q5", "Q4167410", "Q11424", "Q101352", "Q202444", "Q3305213", "Q13442814", "Q7725634", "Q4167836"}
EXCH = {"New York Stock Exchange": "NYSE", "Nasdaq": "NASDAQ", "NASDAQ": "NASDAQ", "London Stock Exchange": "LSE", "Tokyo Stock Exchange": "TSE",
        "Euronext Paris": "EPA", "Euronext Amsterdam": "AMS", "Frankfurt Stock Exchange": "FRA", "Xetra": "XETRA", "SIX Swiss Exchange": "SIX",
        "Toronto Stock Exchange": "TSX", "Australian Securities Exchange": "ASX", "Hong Kong Stock Exchange": "HKEX", "Stockholm Stock Exchange": "STO",
        "Nasdaq Stockholm": "STO", "Nasdaq Copenhagen": "CPH", "Nasdaq Helsinki": "HEL", "Oslo Børs": "OSL", "Borsa Italiana": "BIT",
        "Bolsa de Madrid": "BME", "Korea Exchange": "KRX", "Shanghai Stock Exchange": "SSE", "Shenzhen Stock Exchange": "SZSE",
        "Taiwan Stock Exchange": "TWSE", "National Stock Exchange of India": "NSE", "Bombay Stock Exchange": "BSE", "BSE": "BSE",
        "Singapore Exchange": "SGX", "Euronext Brussels": "EBR", "Euronext": "EURONEXT", "Nasdaq Nordic": "NASDAQ NORDIC"}


def get(url, params, tries=6):
    for i in range(tries):
        wait = GAP - (time.time() - _last[0])
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
        try:
            r = S.get(url, params=params, timeout=40)
        except requests.RequestException as e:
            time.sleep(3 * (i + 1)); continue
        if r.status_code == 429 or r.status_code >= 500:
            ra = r.headers.get("Retry-After"); time.sleep(min(60, float(ra)) if ra and ra.replace(".", "").isdigit() else 5 * (i + 1) ** 1.5); continue
        if r.status_code != 200: return None
        try: return r.json()
        except ValueError: time.sleep(3); continue
    return None


def load_cache():
    try:
        with open(CACHE) as f: c = json.load(f)
    except Exception: c = {}
    for k in ("search", "ent", "extract", "label", "sparql"): c.setdefault(k, {})
    return c


def save_cache(c):
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f: json.dump(c, f, ensure_ascii=False)
    os.replace(tmp, CACHE)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t not in STOP]
    return " ".join(toks)


def clean_name(n):  # "Alphabet (Google)" -> "Alphabet"
    return re.sub(r"\s*\(.*?\)\s*", " ", n or "").strip()


def regdomain(host):
    host = re.sub(r"^https?://", "", (host or "").lower()).split("/")[0].split(":")[0]
    p = host.split(".")
    if len(p) >= 3 and p[-2] in ("co", "com", "org", "net", "gov", "ac") and len(p[-1]) == 2: return ".".join(p[-3:])
    return ".".join(p[-2:]) if len(p) >= 2 else host


def claim_vals(ent, pid):
    return [c for c in ent.get("claims", {}).get(pid, []) if c.get("rank") != "deprecated" and c.get("mainsnak", {}).get("snaktype") == "value"]


def best(stmts):
    pref = [s for s in stmts if s.get("rank") == "preferred"]
    return (pref or stmts)


def qual_time(st, pid="P585"):
    for q in st.get("qualifiers", {}).get(pid, []):
        t = q.get("datavalue", {}).get("value", {}).get("time")
        if t: return t
    return ""


def trim_entity(e):
    """Reduce a wbgetentities entity to the fields we use (keeps the cache small)."""
    lb = e.get("labels", {})
    out = {"id": e.get("id"), "label": (lb.get("en") or lb.get("mul") or {}).get("value") or e.get("sitelinks", {}).get("enwiki", {}).get("title"),
           "desc": e.get("descriptions", {}).get("en", {}).get("value"),
           "aliases": [a["value"] for a in e.get("aliases", {}).get("en", [])],
           "p31": [c["mainsnak"]["datavalue"]["value"]["id"] for c in claim_vals(e, "P31") if isinstance(c["mainsnak"]["datavalue"]["value"], dict)],
           "websites": [c["mainsnak"]["datavalue"]["value"] for c in best(claim_vals(e, "P856"))],
           "enwiki": e.get("sitelinks", {}).get("enwiki", {}).get("title"), "nsite": len(e.get("sitelinks", {})),
           "company_like": any(p in e.get("claims", {}) for p in ("P856", "P1128", "P249", "P414", "P452", "P159", "P571", "P169"))}
    emp = claim_vals(e, "P1128")
    emp = best(emp)
    if emp:
        emp = sorted(emp, key=lambda s: qual_time(s))[-1]
        try: out["employees"] = int(float(emp["mainsnak"]["datavalue"]["value"]["amount"]))
        except Exception: pass
    fnd = best(claim_vals(e, "P571"))
    if fnd:
        try: out["founded"] = int(fnd[0]["mainsnak"]["datavalue"]["value"]["time"][1:5])
        except Exception: pass
    tick = []
    for s in best(claim_vals(e, "P414")):
        if "P582" in s.get("qualifiers", {}): continue  # ended listing
        sym = next((q["datavalue"]["value"] for q in s.get("qualifiers", {}).get("P249", []) if q.get("datavalue")), None)
        ex = s["mainsnak"]["datavalue"]["value"].get("id")
        if sym and ex: tick.append([ex, sym])
    if not tick:
        for s in claim_vals(e, "P249"): tick.append([None, s["mainsnak"]["datavalue"]["value"]])
    out["tickers"] = tick
    logo = best(claim_vals(e, "P154")) or best(claim_vals(e, "P8972"))
    if logo:
        out["logo"] = logo[0]["mainsnak"]["datavalue"]["value"]
    return out


SPARQL = "https://query.wikidata.org/sparql"


def sparql_candidates(c, names):
    """Batch label/alias lookup via SPARQL (exact label or altLabel, en or mul) restricted to items with an English Wikipedia article.
    ~10 queries for ~400 names instead of ~800 rate-limited API calls.  Results cached per name in c['sparql']."""
    todo = [n for n in dict.fromkeys(names) if n and n not in c["sparql"]]
    for i in range(0, len(todo), 30):
        chunk = todo[i:i + 30]
        vals = " ".join(f'"{n.replace(chr(92), "").replace(chr(34), "")}"@{lg}' for n in chunk for lg in ("en", "mul"))
        q = ("SELECT ?item ?l WHERE { VALUES ?l { " + vals + " } ?item rdfs:label|skos:altLabel ?l . "
             "?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . "
             "FILTER EXISTS { ?item wdt:P856|wdt:P1128|wdt:P414|wdt:P249|wdt:P452 ?x } }")
        j = None
        for t in range(4):
            wait = GAP - (time.time() - _last[0])
            if wait > 0: time.sleep(wait)
            _last[0] = time.time()
            try:
                r = S.get(SPARQL, params=dict(query=q, format="json"), timeout=90)
                if r.status_code == 200: j = r.json(); break
                time.sleep(5 * (t + 1))
            except Exception: time.sleep(5 * (t + 1))
        if j is None: continue
        got = {n: [] for n in chunk}
        for b in j["results"]["bindings"]:
            lab = b["l"]["value"]; qid = b["item"]["value"].rsplit("/", 1)[1]
            if lab in got and qid not in got[lab]: got[lab].append(qid)
        for n, ids in got.items(): c["sparql"][n] = ids[:12]


def search(c, q):
    if q in c["search"]: return c["search"][q]
    j = get(API, dict(action="wbsearchentities", search=q, language="en", uselang="en", type="item", limit=6, format="json"))
    if j is None: return None  # not cached -> retried next run
    ids = [x["id"] for x in j.get("search", [])]
    c["search"][q] = ids
    return ids


def fetch_entities(c, qids):
    need = [q for q in dict.fromkeys(qids) if q not in c["ent"]]
    for i in range(0, len(need), 40):
        chunk = need[i:i + 40]
        j = get(API, dict(action="wbgetentities", ids="|".join(chunk), props="labels|descriptions|aliases|claims|sitelinks", languages="en|mul", format="json"))
        if not j: continue
        for qid, e in j.get("entities", {}).items():
            c["ent"][qid] = trim_entity(e) if "missing" not in e else {"id": qid, "missing": True}
    return [c["ent"].get(q) for q in qids]


BAD_DESC = re.compile(r"\b(newspaper|magazine|city|county|town|village|municipality|township|river|film|album|band|football|cricket|club|school|university|surname|given name|constituency|settlement|"
                      r"human|disambiguation|television|tv series|song|novel|video game|airport|district|neighbou?rhood|commune|species|genus)\b", re.I)
CO_DESC = re.compile(r"\b(company|corporation|multinational|bank|firm|manufacturer|retailer|conglomerate|insurer|insurance|business|limited|plc|group|holding|provider|maker|enterprise|consultancy|"
                     r"services|technology|software|pharmaceutical|chain|brand|fund|asset manager|exchange|airline|carrier|producer|supplier|operator|video game|developer|publisher|distributor)\b", re.I)


def score(ent, name_variants, domain):
    """Return (score, method) or (0, None)."""
    if not ent or ent.get("missing"): return 0, None
    if set(ent.get("p31", [])) & NOT_COMPANY_P31: return 0, None
    if BAD_DESC.search(ent.get("desc") or "") and not CO_DESC.search(ent.get("desc") or ""): return 0, None
    company_ev = bool(ent.get("employees") or ent.get("tickers") or CO_DESC.search(ent.get("desc") or ""))
    lab = norm(ent.get("label") or ent.get("enwiki"))
    label_eq = bool(lab) and lab in name_variants
    dom = regdomain(domain)
    dom_eq = any(regdomain(w) == dom for w in ent.get("websites", [])) if dom else False
    toks = set(lab.split())
    overlap = any(toks & set(v.split()) for v in name_variants if v)
    alias_eq = any(norm(a) in name_variants for a in ent.get("aliases", []))
    if dom_eq and (label_eq or overlap or alias_eq): return 100 + (50 if label_eq else 0) + min(ent.get("nsite", 0), 300) / 100, "domain"
    sld = lambda h: regdomain(h).split(".")[0]
    acr_alias = any(a.isupper() and len(a) >= 3 and norm(a) in name_variants for a in ent.get("aliases", []))
    starts = any(lab.startswith(v + " ") for v in name_variants if v)
    # same second-level domain on a different TLD (takeda.com vs takeda.co.jp) + name overlap + a real Wikipedia article
    if dom and any(sld(w) == sld(dom) for w in ent.get("websites", [])) and ent.get("enwiki") and ent.get("company_like") and company_ev and (label_eq or starts or acr_alias):
        return 80 + min(ent.get("nsite", 0), 300) / 100, "domain-tld"
    if label_eq and ent.get("enwiki") and ent.get("company_like") and company_ev: return 50 + min(ent.get("nsite", 0), 300) / 100, "label"
    # 'Ferguson' -> 'Ferguson Enterprises': label starts with our name AND the entity is a listed / sized company with an English article
    if starts and ent.get("enwiki") and (ent.get("tickers") or ent.get("employees")): return 45 + min(ent.get("nsite", 0), 300) / 100, "label"
    if False: return 50 + min(ent.get("nsite", 0), 300) / 100, "label"
    return 0, None


def resolve(c, parent, name, domain, slow=True):
    variants = {v for v in (norm(parent), norm(clean_name(parent)), norm(name)) if v}
    # "Alphabet (Google)" -> also the bracketed part is NOT trusted as a name (could be the owner), only as search hint
    queries = [x for x in dict.fromkeys([parent, clean_name(parent)]) if x]
    def run(cand):
        ents = fetch_entities(c, cand)
        b = (0, None, None)
        for qid, ent in zip(cand, ents):
            sc, how = score(ent, variants, domain)
            if sc > b[0]: b = (sc, how, qid)
        return b
    cand = [q for x in queries for q in c["sparql"].get(x, [])]
    b = run(cand) if cand else (0, None, None)
    if b[1] is None and slow:                       # fallback: wbsearchentities (slower, rate limited)
        cand2 = []
        for q in queries:
            ids = search(c, q)
            if ids is None: return "retry", None
            cand2 += ids
        b = run(cand2)
    return b[1], b[2]


def short_exchange(c, exid):
    if not exid: return None
    lab = c["label"].get(exid)
    if lab is None:
        j = get(API, dict(action="wbgetentities", ids=exid, props="labels", languages="en", format="json"))
        lab = (j or {}).get("entities", {}).get(exid, {}).get("labels", {}).get("en", {}).get("value") if j else None
        if lab: c["label"][exid] = lab
    return EXCH.get(lab, lab)


def build_ticker(c, ent):
    for exid, sym in ent.get("tickers", []):
        ex = short_exchange(c, exid)
        return f"{ex}: {sym}" if ex else sym
    return None


def first_sentences(text, n=2, cap=320):
    text = re.sub(r"\s*\([^()]*\)", "", text or "")            # drop pronunciation / date parentheses
    text = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    out = ""
    for s in sents[:n]:
        if len(out) + len(s) > cap and out: break
        out = (out + " " + s).strip()
    return out[:cap].rsplit(" ", 1)[0] + "…" if len(out) > cap else out


def fetch_extracts(c, titles):
    need = [t for t in dict.fromkeys(titles) if t not in c["extract"]]
    for i in range(0, len(need), 20):
        chunk = need[i:i + 20]
        j = get(WPAPI, dict(action="query", prop="extracts", exintro=1, explaintext=1, redirects=1, titles="|".join(chunk), format="json", formatversion=2))
        if not j: continue
        q = j.get("query", {})
        back = {}
        for n in q.get("normalized", []) + q.get("redirects", []): back[n["to"]] = n["from"]
        got = {}
        for p in q.get("pages", []):
            t = p.get("title"); ex = p.get("extract")
            orig = t
            while orig in back: orig = back[orig]
            got[orig] = ex or ""
            got[t] = ex or ""
        for t in chunk:
            c["extract"][t] = first_sentences(got.get(t, ""))


def aliases_for(name, parent, ent):
    out = []
    def add(x):
        x = (x or "").strip()
        if len(x) < 2 or len(x) > 40 or not re.search(r"[A-Za-z]", x) or re.search(r"[^\x00-\x7f]", x): return
        if x.lower() not in {o.lower() for o in out}: out.append(x)
    add(parent); add(clean_name(parent)); add(name)
    base = re.sub(r"\s+(India|GCC|Global Services|Technologies India|USI India|USI)$", "", name or "", flags=re.I)
    add(base)
    if ent:
        add(ent.get("label"))
        for a in ent.get("aliases", []): add(a)
    return out[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int); ap.add_argument("--dry", action="store_true"); ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    c = {"search": {}, "ent": {}, "extract": {}, "label": {}, "sparql": {}} if a.refresh else load_cache()
    for k in ("search", "ent", "extract", "label", "sparql"): c.setdefault(k, {})
    DSN = os.environ.get("DATABASE_URL", "postgresql://gcc:gcc@localhost/gcc")
    # read rows with autocommit and close BEFORE any network call (never hold a transaction across HTTP)
    with psycopg.connect(DSN, autocommit=True) as rc:
        rows = rc.execute("SELECT id,name,parent_company,domain FROM companies ORDER BY id").fetchall()
    if a.limit: rows = rows[:a.limit]
    if True:
        res = {}; t0 = time.time()
        allq = [x for _, name, parent, _d in rows for x in (parent or name, clean_name(parent or name))]
        sparql_candidates(c, allq); save_cache(c)
        print(f"sparql candidates for {len(c['sparql'])} names ({time.time() - t0:.0f}s)", flush=True)
        all_c = [q for x in allq for q in c["sparql"].get(x, [])]
        fetch_entities(c, all_c); save_cache(c)
        print(f"entities cached: {len(c['ent'])} ({time.time() - t0:.0f}s)", flush=True)
        for n, (cid, name, parent, domain) in enumerate(rows, 1):
            how, qid = resolve(c, parent or name, name, domain)
            res[cid] = (how, qid)
            if n % 25 == 0:
                save_cache(c); print(f"  {n}/{len(rows)} resolved ({time.time() - t0:.0f}s)", flush=True)
        save_cache(c)
        titles = [c["ent"][q]["enwiki"] for h, q in res.values() if q and c["ent"].get(q, {}).get("enwiki")]
        fetch_extracts(c, titles); save_cache(c)
        report = []; matched = 0; methods = {}; writes = []
        for cid, name, parent, domain in rows:
            how, qid = res[cid]
            ent = c["ent"].get(qid) if qid and how in ("domain", "domain-tld", "label") else None
            if ent:
                matched += 1; methods[how] = methods.get(how, 0) + 1
                site = next((w for w in ent.get("websites", [])), None)
                wp = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(ent["enwiki"].replace(" ", "_"), safe="_(),'") if ent.get("enwiki") else None
                desc = c["extract"].get(ent.get("enwiki") or "", "") or (ent.get("desc") or "").capitalize() or None
                if desc and not c["extract"].get(ent.get("enwiki") or "") and ent.get("desc"):
                    desc = f"{ent['label']}: {ent['desc']}."
                logo = ("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(ent["logo"].replace(" ", "_")) + "?width=120") if ent.get("logo") else None
                vals = dict(wikidata_id=qid, wikipedia_url=wp, description=desc, global_employees=ent.get("employees"), founded_year=ent.get("founded"),
                            website=site, ticker=build_ticker(c, ent), logo_url=logo, aliases=aliases_for(name, parent, ent))
            else:
                vals = dict(wikidata_id=None, wikipedia_url=None, description=None, global_employees=None, founded_year=None, website=None, ticker=None, logo_url=None,
                            aliases=aliases_for(name, parent, None))   # unmatched: leave blank (also clears stale values from earlier runs)
            report.append(dict(id=cid, name=name, parent=parent, method=how if ent else None, qid=qid if ent else None,
                               label=ent.get("label") if ent else None, **{k: v for k, v in vals.items() if k in ("website", "ticker", "global_employees", "founded_year")}))
            if not a.dry:
                writes.append((f"UPDATE companies SET {', '.join(f'{k}=%s' for k in vals)} WHERE id=%s", list(vals.values()) + [cid]))
        save_cache(c)
        if writes:   # short-lived autocommit connection: each UPDATE commits immediately
            with psycopg.connect(DSN, autocommit=True) as wc:
                for sql, args in writes: wc.execute(sql, args)
        with open(REPORT, "w") as f: json.dump(report, f, indent=1, ensure_ascii=False)
        tot = len(rows)
        print(f"matched {matched}/{tot} ({100 * matched / tot:.1f}%)  methods={methods}")
        with psycopg.connect(DSN, autocommit=True) as rc:
            for k in ("description", "global_employees", "founded_year", "website", "ticker", "logo_url", "wikipedia_url"):
                print(f"  {k}: ", rc.execute(f"SELECT count({k}) FROM companies").fetchone()[0])


if __name__ == "__main__":
    main()
