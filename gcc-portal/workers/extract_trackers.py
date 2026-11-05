"""Fill the two trackers from headlines we already store (headline + link only, never article text).

people_moves  <- articles.category='leadership' (GCC-relevant appointments)
    Patterns (title is first stripped of " - Publisher" / " | Publisher" tails):
      A  <Person> appointed|named|elevated|promoted|designated [as|to] <Role> at|with|of <Company>
      B  <Company> appoints|names|elevates|promotes|hires|taps|picks <Person> as|to lead|to head <Role>
      C  <Person> joins <Company> as <Role>
      D  <Person> takes charge as|of <Role> at <Company>
    A row is written only when person, role AND company are all parsed and pass validation
    (2-4 capitalised name tokens, no organisation words in the name, a role keyword in the role). Otherwise skipped, never guessed.
    city = explicit city in the headline (classify.detect_city); company_id via link_articles term matching.

fundings      <- funding headlines about GCC-ecosystem players: GCC-enablement / GCC-services startups (ANSR, Zinnov, Inductus, GCC-as-a-service ...),
    GCC-focused funds, or deals explicitly linked to GCCs.  Sources: (1) articles already stored with category='funding' that pass the relevance gate,
    (2) with --fetch, a few targeted Google News RSS queries (headline/link/date only).  Requires a raise/invest pattern AND a GCC-ecosystem signal;
    Gulf "GCC" items are rejected.  amount_text / round / investors are only filled when explicit in the headline.

Run: python workers/extract_trackers.py [--fetch] [--dry]
"""
import os, re, sys, time, email.utils, urllib.parse, xml.etree.ElementTree as ET
import psycopg, requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from relevance import is_relevant, GULF, GULF_PLACE
from classify import detect_city
import link_articles

DSN = os.environ.get("DATABASE_URL", "postgresql://gcc:gcc@localhost/gcc")

# ------------------------------------------------------------------ people
NAME_TOK = r"(?:[A-Z][A-Za-z'’.\-]*|[A-Z]\.?)"
NAME = rf"(?:(?:Dr|Mr|Ms|Mrs|Prof|Shri|Smt)\.?\s+)?{NAME_TOK}(?:\s+{NAME_TOK}){{1,3}}"
VERB_A = r"(?i:(?:has\s+been\s+|is\s+|gets\s+)?(?P<verb>appointed|named|elevated|promoted|designated|re-?designated|announced|picked|tapped))"
VERB_B = r"(?i:(?P<verb>appoints|names|elevates|promotes|hires|taps|picks|announces|designates))"
TAIL = re.compile(r"\s+[-|–—]\s+(?:https?://\S+|[A-Z][\w .&']{2,45})\s*$")
ROLE_KW = re.compile(r"\b(head|director|vp|vice president|president|ceo|cto|cio|cfo|coo|cmo|chro|chief|md|managing|lead|leader|partner|manager|gm|general manager|officer|chair\w*|svp|evp|avp|"
                     r"site|country|hr|principal|executive|founder|advisor|adviser)\b", re.I)
ORG_WORD = re.compile(r"\b(global|capability|centre|center|gcc|india|group|bank|limited|ltd|pvt|private|inc|corp|corporation|technologies|technology|solutions|services|systems|partners|capital|"
                      r"financial|insurance|industries|enterprises|health|healthcare|labs|software|digital|consulting|international|holdings|pharma|motors|airlines|management)\b", re.I)
GENERIC_SUBJ = re.compile(r"^(?:how|why|what|top|new|india|indian|gcc|gccs|these|here|meet|who|will)\b", re.I)


def clean_title(t):
    t = (t or "").strip()
    for _ in range(2): t = TAIL.sub("", t)
    return t.strip()


def good_person(p):
    p = (p or "").strip().strip(",")
    toks = p.split()
    if not (2 <= len(toks) <= 5): return None
    core = [x for x in toks if not re.match(r"^(Dr|Mr|Ms|Mrs|Prof|Shri|Smt)\.?$", x)]
    if len(core) < 2 or ORG_WORD.search(" ".join(core)) or any(not x[0].isupper() for x in core): return None
    return p


def clean_role(r):
    r = re.sub(r"\s+", " ", (r or "")).strip(" ,;:-–—")
    r = re.sub(r"^(?:the\s+)?(?:new\s+)?", "", r, flags=re.I)
    m = re.match(r"^(?:to\s+)?(?:lead|run|steer|spearhead)\s+(?:the\s+|its\s+)*(.+)$", r, re.I)
    if m: r = "Head, " + m.group(1)
    r = re.sub(r"\s*,?\s*(?:amid|as|to|while|after|following)\s+(?:ai|gcc|its|the|growth|expansion|enterprise|drive|scale|strengthen|support|accelerate|build|lead|steer|spearhead)\b.*$", "", r, flags=re.I)
    r = re.sub(r"\s+in\s+(?:Bengaluru|Bangalore|Hyderabad|Pune|Chennai|Mumbai|Gurugram|Noida|Kolkata|Delhi\s*NCR|Ahmedabad|Coimbatore)\b.*$", "", r, flags=re.I)
    r = r[:120].strip(" ,;:-–—")
    return r if len(r.split()) >= 2 or r.lower() in ("ceo", "cto", "cio", "cfo", "coo", "md") else None


def clean_company(c):
    c = re.sub(r"\s+", " ", (c or "")).strip(" ,;:-–—.")
    c = re.sub(r"\s+in\s+(?:Bengaluru|Bangalore|Hyderabad|Pune|Chennai|Mumbai|Gurugram|Gurgaon|Noida|Kolkata|Delhi\s*NCR|Ahmedabad|Coimbatore|India)\b.*$", "", c, flags=re.I)
    c = re.sub(r"\s+(?:global capability cent(?:er|re)s?(?:\s*\(GCC\))?|GCCs?|India GCC)$", "", c, flags=re.I)
    c = re.sub(r"^(?:the\s+)", "", c, flags=re.I)
    c = c.strip(" ,;:-–—.")
    return c if 2 <= len(c) <= 60 and len(c.split()) <= 6 and not GENERIC_SUBJ.match(c) else None


KIND = {"appointed": "appointed", "named": "appointed", "appoints": "appointed", "names": "appointed", "hires": "appointed", "taps": "appointed", "picks": "appointed",
        "announces": "appointed", "designates": "appointed", "designated": "appointed", "picked": "appointed", "tapped": "appointed", "announced": "appointed",
        "elevated": "promoted", "promoted": "promoted", "elevates": "promoted", "promotes": "promoted", "joins": "joined", "takes": "appointed"}

PAT_A = re.compile(rf"^(?P<person>{NAME})\s+{VERB_A}\s+(?:as\s+|to\s+)?(?P<rest>.+)$")
PAT_B = re.compile(rf"^(?P<company>.+?)\s+{VERB_B}\s+(?P<person>{NAME})\s+(?P<lead>(?i:as|to\s+(?:lead|head|run|steer)|for))\s+(?P<role>.+)$")
PAT_C = re.compile(rf"^(?P<person>{NAME})\s+(?i:joins|has\s+joined|joined)\s+(?P<company>.+?)\s+(?i:as)\s+(?P<role>.+)$")
PAT_D = re.compile(rf"^(?P<person>{NAME})\s+(?i:takes\s+(?:over|charge)\s+(?:as|of))\s+(?P<rest>.+)$")


def split_rest(rest):
    """'<Role> at <Company>' -> (role, company); handles 'Head of Orbia Global Capability Center in Pune' style too."""
    rest = rest.strip()
    m = re.match(r"^(?P<role>.+?)\s+(?:at|with)\s+(?P<company>[A-Z0-9].+)$", rest)
    if m: return m.group("role"), m.group("company")
    m = re.match(r"^(?P<role>(?:Global\s+)?(?:Head|Director|Lead|Leader|Chief[\w ]*|CEO|Managing Director|Vice President|VP|President)[\w ,&/–-]*?)\s+of\s+(?P<company>[A-Z0-9][\w&.' -]*?)\s+(?:Global Capability|Capability|GCC|India)\b.*$", rest)
    if m:
        role = m.group("role")
        if len(role.split()) < 2: role = f"{role} of {m.group('company')} Global Capability Centre"
        return role, m.group("company")
    return None, None


def parse_move(title):
    t = clean_title(title)
    m = PAT_B.match(t)
    if m and "," not in m.group("company") and ";" not in m.group("company"):
        # company first.  The person must still look like a person.
        p = good_person(m.group("person")); co = clean_company(m.group("company"))
        raw = m.group("role")
        if m.group("lead").lower().startswith("to"): raw = "lead " + raw
        ro = clean_role(raw)
        if p and co and ro and ROLE_KW.search(ro): return p, ro, co, KIND.get(m.group("verb").lower(), "appointed")
    for pat, kind_from in ((PAT_A, "verb"), (PAT_D, None)):
        m = pat.match(t)
        if m:
            role, comp = split_rest(m.group("rest"))
            p = good_person(m.group("person")); co = clean_company(comp) if comp else None; ro = clean_role(role) if role else None
            if p and co and ro and ROLE_KW.search(ro):
                return p, ro, co, KIND.get((m.groupdict().get("verb") or "takes").lower(), "appointed")
    m = PAT_C.match(t)
    if m:
        p = good_person(m.group("person")); co = clean_company(m.group("company")); ro = clean_role(m.group("role"))
        if p and co and ro and ROLE_KW.search(ro): return p, ro, co, "joined"
    return None


# ------------------------------------------------------------------ funding
RAISE = re.compile(r"\b(raises?|raised|raising|secures?|bags?|bagged|closes|lands|gets|mops up|attracts|receives|funding|series\s+[a-g]\b|seed\s+(?:round|funding)|pre-seed|"
                   r"invests?|invested|investment in|backs?|backed)\b", re.I)
ROUND = re.compile(r"\b(pre-seed|seed|pre-series\s+[a-d]|series\s+[a-g]\+?|bridge round|growth round|venture debt|debt funding|strategic investment|minority (?:stake|investment))\b", re.I)
AMOUNT = re.compile(r"((?:US\$|USD\s?|\$|₹|Rs\.?\s?|INR\s?)\s?[\d][\d,.]*\s?(?:million|mn|m|billion|bn|b|crore|cr|lakh|k)?\b)", re.I)
ECO = re.compile(r"\b(ansr|zinnov|inductus|gcc[- ]as[- ]a[- ]service|gcc enablement|gcc enabler|gcc platform|gcc startup|gcc services|capability cent(?:er|re)s?|build[- ]operate[- ]transfer|\bBOT\b model|"
                 r"gcc[- ]focused|gcc fund|offshore development cent(?:er|re)s?|\bgccs?\b)", re.I)
FUNDING_QUERIES = ['ANSR GCC raises funding', 'ANSR investment GCC platform', 'GCC startup raises India "capability centre"', '"GCC-as-a-service" raises',
                   'GCC enablement platform funding India', 'Inductus GCC funding', 'Zinnov funding GCC', '"global capability center" startup "Series A"',
                   'GCC focused fund India launch', '"capability center" startup raises seed India', 'GCC "raises" funding startup "capability centres" India 2026',
                   '"GCC" platform startup "raises" million India talent capability', 'Quintes Global funding', 'GCC advisory firm investment stake India', '"GCC" "Series B" India',
                   'private equity invests GCC services firm India']


def parse_funding(title):
    t = clean_title(title)
    if not RAISE.search(t) or not ECO.search(t): return None
    if GULF.search(t) or re.search(r"\bGCC\b.{0,15}\b(and|&)\b.{0,8}\b(UK|US|MENA|Europe)\b|\bIndia, GCC\b|GCC region", t, re.I): return None
    if GULF_PLACE.search(t) and not re.search(r"\bindia\b|\bindian\b", t, re.I): return None
    am = AMOUNT.search(t); rd = ROUND.search(t)
    company = None; investors = None; kind = "funding"
    m = re.match(r"^(?P<inv>.+?)\s+(?:invests?|backs?|leads?)\s+(?:\S+\s+){0,2}?(?:[$₹]\s?[\d.,]+\s?\w*\s+)?(?:in|into)\s+(?:(?:GCC|capability[\w -]*?)\s+(?:platform|startup|firm|player)\s+)?(?P<co>[A-Z][\w&.' -]{1,40}?)(?:\s+[-|–—]\s+.*|,.*)?$", t)
    if m:
        company, investors, kind = m.group("co").strip(), m.group("inv").strip(), "investment"
    else:
        m = re.match(r"^(?P<co>[A-Z][\w&.' -]{1,40}?)\s+(?:raises?|raised|secures?|bags?|bagged|closes|lands|gets|mops up|attracts|receives)\b", t)
        if m: company = m.group("co").strip()
        m2 = re.search(r"\b(?:led by|from|backed by|with participation from)\s+(?P<inv>[A-Z][\w&.' ,/-]{2,80}?)(?:\s+[-|–—]\s+|$|\.|;)", t)
        if m2: investors = m2.group("inv").strip(" ,")
    if company: company = re.sub(r"^\S+-backed\s+(?:\w+\s+)?", "", company).strip()
    if not company or GENERIC_SUBJ.match(company): return None
    return dict(company_name=company, kind=kind, amount_text=am.group(1).strip() if am else None, round=rd.group(1) if rd else None, investors=investors)


def fetch_rss(q):
    for attempt in range(3):
        try:
            r = requests.get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-IN&gl=IN&ceid=IN:en", timeout=25,
                             headers={"User-Agent": "Mozilla/5.0 (gcc-portal tracker)"})
            if r.status_code == 200:
                out = []
                for it in ET.fromstring(r.content).iter("item"):
                    pd = it.findtext("pubDate"); src = it.find("source")
                    out.append((it.findtext("title") or "", it.findtext("link"), email.utils.parsedate_to_datetime(pd) if pd else None,
                                src.text if src is not None else None))
                return out
        except Exception: pass
        time.sleep(2 * (attempt + 1))
    return []


def main():
    dry = "--dry" in sys.argv
    conn = psycopg.connect(DSN, autocommit=True)
    comps = conn.execute("SELECT id,name,parent_company,aliases FROM companies").fetchall()
    terms = link_articles.build(comps)
    arts = conn.execute("SELECT id,title,source_url,published_at,company_id,city FROM articles WHERE category='leadership' AND coalesce(relevant,true) ORDER BY published_at DESC").fetchall()
    seen = set(); moves = []; skipped = 0
    for aid, title, url, at, cid, city in arts:
        r = parse_move(title)
        if not r: skipped += 1; continue
        person, role, company, kind = r
        key = (person.lower(), re.sub(r"[^a-z0-9]", "", company.lower())[:12])
        if key in seen: continue                                  # same appointment reported by several outlets
        seen.add(key)
        co_id = link_articles.match(company, terms) or cid
        moves.append(dict(person=person, role=role, company_name=company, company_id=co_id, city=detect_city(title), kind=kind, source_url=url, published_at=at))
    print(f"people_moves: {len(arts)} leadership headlines -> {len(moves)} parsed, {skipped} skipped (not parseable with confidence)")
    # ---- fundings
    fund = []; seenf = set()
    cands = [(t, u, a, None) for _, t, u, a, _c, _ci in conn.execute("SELECT id,title,source_url,published_at,company_id,city FROM articles WHERE category='funding'").fetchall()]
    if "--fetch" in sys.argv:
        for q in FUNDING_QUERIES:
            for t, u, a, src in fetch_rss(q):
                title = re.sub(r"\s+-\s+" + re.escape(src or "~~") + r"$", "", t)
                cands.append((title, u, a, src)); time.sleep(1.0)
    for title, url, at, _ in cands:
        f = parse_funding(title)
        if not f or not url: continue
        k = (re.sub(r"[^a-z0-9]", "", f["company_name"].lower()), str(at)[:10])
        if k in seenf: continue
        seenf.add(k)
        fund.append(dict(f, summary=clean_title(title)[:240], source_url=url, published_at=at))
    print(f"fundings: {len(cands)} candidate headlines -> {len(fund)} accepted")
    for m in moves[:10]: print("  MOVE", m["person"], "|", m["role"], "|", m["company_name"], "|", m["city"], "|", m["kind"], "|", str(m["published_at"])[:10])
    for f in fund[:10]: print("  FUND", f["company_name"], "|", f["amount_text"], "|", f["round"], "|", f["investors"], "|", str(f["published_at"])[:10], "|", f["summary"][:80])
    if dry: return
    for m in moves:
        conn.execute("INSERT INTO people_moves(person,role,company_name,company_id,city,kind,source_url,published_at) VALUES(%(person)s,%(role)s,%(company_name)s,%(company_id)s,%(city)s,%(kind)s,%(source_url)s,%(published_at)s) "
                     "ON CONFLICT(source_url) DO UPDATE SET person=EXCLUDED.person, role=EXCLUDED.role, company_name=EXCLUDED.company_name, company_id=EXCLUDED.company_id, city=EXCLUDED.city, kind=EXCLUDED.kind", m)
    for f in fund:
        conn.execute("INSERT INTO fundings(company_name,kind,amount_text,round,investors,summary,source_url,published_at) VALUES(%(company_name)s,%(kind)s,%(amount_text)s,%(round)s,%(investors)s,%(summary)s,%(source_url)s,%(published_at)s) "
                     "ON CONFLICT(source_url) DO UPDATE SET company_name=EXCLUDED.company_name, amount_text=EXCLUDED.amount_text, round=EXCLUDED.round, investors=EXCLUDED.investors, summary=EXCLUDED.summary", f)
    print("written:", conn.execute("SELECT count(*) FROM people_moves").fetchone()[0], "people_moves,", conn.execute("SELECT count(*) FROM fundings").fetchone()[0], "fundings")


if __name__ == "__main__":
    main()
