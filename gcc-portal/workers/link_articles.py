"""Link articles (and expansions) to companies by matching names / parents / aliases in the HEADLINE.

Rules (transparent):
  * Terms per company = company name, parent_company (raw + without "(…)"), simple de-suffixed variants
    ("Infineon Technologies" -> "Infineon", "The Home Depot" -> "Home Depot"), and Wikidata aliases.
  * A term that maps to MORE THAN ONE company is dropped (unless it is that company's exact name/parent).
  * Matching is on word boundaries, never substring ("Target" must not hit "Targets").
  * STRONG terms (>= 5 chars, not in the ambiguous list): case-insensitive match is enough.
  * AMBIGUOUS terms (<= 4 chars, or in AMBIGUOUS: Target, Visa, Intel, Apple, Oracle, Shell, Meta, ...):
        - must match with the exact capitalisation of the canonical form ("Visa", not "visa"),
        - title must carry GCC / India context (GCC, capability cent*, India, an Indian city),
        - must not be followed by a digit or by a non-company word (Visa rules/fee/..., Apple pie ...).
  * If several companies match, the one whose term appears EARLIEST in the headline wins (headline subject).
  * Whole table is recomputed; result is written only if it differs. Run: python workers/link_articles.py [--dry]
"""
import os, re, sys
import psycopg

DSN = os.environ.get("DATABASE_URL", "postgresql://gcc:gcc@localhost/gcc")
AMBIGUOUS = {w.lower() for w in """target visa intel apple oracle shell gap meta arm ford continental principal discover carrier waters sage chase
vanguard pearson cummins brookfield amadeus standard eaton linde sabre infor genesys stripe workday snowflake aon citi equinor""".split()} - {"equinor"}
CONTEXT = re.compile(r"\b(gccs?|capability cent(?:er|re)s?|india|indian|bengaluru|bangalore|hyderabad|pune|chennai|mumbai|delhi|gurugram|gurgaon|noida|kolkata|ahmedabad|coimbatore|kochi|"
                     r"gift city|global in-house)\b", re.I)
NEG_NEXT = re.compile(r"^\W*(rules?|policy|policies|fees?|applications?|on arrival|free|restrictions?|ban|extension|appointments?|interviews?|pie|juice|"
                      r"card|cards|payments?|stock|spots?|ceasefire|talks)\b", re.I)
SUFFIX = re.compile(r"\s+(inc\.?|corp\.?|corporation|plc|company|co\.?|group|holdings?|technologies|technology|platforms|ltd\.?|limited|ag|se|sa|n\.v\.)$", re.I)
INDIA_TAIL = re.compile(r"\s+(india|gcc|global services|usi india|usi)$", re.I)


def variants(name, parent, aliases):
    """Return {term: kind} where kind 'exact' (name/parent as stored) or 'derived'."""
    out = {}
    def add(t, kind):
        t = (t or "").strip(" .,-")
        if len(t) >= 2 and re.search(r"[A-Za-z]", t) and (t not in out or kind == "exact"): out[t] = kind
    for raw in (name, parent):
        if not raw: continue
        add(raw, "exact"); base = re.sub(r"\s*\(.*?\)\s*", " ", raw).strip(); add(base, "exact")
        m = re.search(r"\((.*?)\)", raw)
        if m and raw is parent and m.group(1) and m.group(1) not in ("IBM", "HPE", "Samsung", "Synopsys"): add(m.group(1), "derived")  # "Alphabet (Google)" -> Google, "Merck & Co. (MSD)" -> MSD
        b = base
        for _ in range(2):
            b2 = SUFFIX.sub("", b).strip(); b2 = re.sub(r"^The\s+", "", b2)
            if b2 != b and len(b2) >= 2: add(b2, "derived"); b = b2
        b3 = INDIA_TAIL.sub("", base).strip()
        if b3 != base: add(b3, "derived")
    for a in aliases or []: add(a, "derived")
    return out


def is_ambiguous(term):
    return len(term) <= 4 or term.lower() in AMBIGUOUS


def build(companies):
    owners = {}
    for cid, name, parent, aliases in companies:
        for t, kind in variants(name, parent, aliases).items():
            owners.setdefault(t.lower(), []).append((cid, t, kind))
    terms = []  # (regex, cid, term, ambiguous)
    for key, lst in owners.items():
        ids = {cid for cid, _, _ in lst}
        if len(ids) > 1:
            lst = [x for x in lst if x[2] == "exact"]       # shared alias: keep only exact name/parent owners
            ids = {cid for cid, _, _ in lst}
            if len(ids) != 1: continue
        cid, term, _ = lst[0]
        amb = is_ambiguous(term)
        flags = 0 if amb else re.I
        terms.append((re.compile(r"(?<![\w&])" + re.escape(term) + r"(?![\w&])", flags), cid, term, amb))
    return terms


def match(title, terms):
    best = None
    has_ctx = bool(CONTEXT.search(title))
    for rx, cid, term, amb in terms:
        m = rx.search(title)
        if not m: continue
        if amb:
            if not has_ctx: continue
            tail = title[m.end():]
            if NEG_NEXT.match(tail) or re.match(r"^\s*\d", tail): continue
        cand = (m.start(), -len(term), cid)
        if best is None or cand < best: best = cand
    return best[2] if best else None


def main():
    dry = "--dry" in sys.argv
    with psycopg.connect(DSN, autocommit=True) as conn:
        comps = conn.execute("SELECT id,name,parent_company,aliases FROM companies").fetchall()
        arts = conn.execute("SELECT id,title,company_id FROM articles").fetchall()
        exps = conn.execute("SELECT id,COALESCE(summary,company_name),company_id FROM expansions").fetchall()
    terms = build(comps)
    print(f"{len(terms)} match terms over {len(comps)} companies")
    changes = {"articles": [], "expansions": []}
    stats = {}
    for label, rows in (("articles", arts), ("expansions", exps)):
        before = sum(1 for r in rows if r[2]); after = 0; moved = 0; lost = 0; gained = 0
        for rid, title, old in rows:
            new = match(title or "", terms)
            after += 1 if new else 0
            if new != old:
                if old and new: moved += 1
                elif old: lost += 1
                else: gained += 1
                changes[label].append((rid, new, old, title))
        stats[label] = dict(total=len(rows), before=before, after=after, gained=gained, moved=moved, lost=lost)
    print(stats)
    names = {c[0]: c[1] for c in comps}
    for label in changes:
        for rid, new, old, title in [x for x in changes[label] if x[2]][:12]:
            print(f"  {label} #{rid} {names.get(old)} -> {names.get(new)}  | {title[:90]}")
    if dry: return
    with psycopg.connect(DSN, autocommit=True) as conn:
        for label, tbl in (("articles", "articles"), ("expansions", "expansions")):
            for rid, new, old, _ in changes[label]:
                conn.execute(f"UPDATE {tbl} SET company_id=%s WHERE id=%s", (new, rid))
    print("written")


if __name__ == "__main__":
    main()
