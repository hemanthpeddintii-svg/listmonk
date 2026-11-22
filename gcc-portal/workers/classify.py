"""Rule-based headline classifier + expansions noise cleaner.  Deterministic, no ML, safe to re-run.

1) articles.category in {funding, leadership, expansion, hiring, policy, ai, other}
   First matching rule wins, in this order (the order IS the policy):
     funding     raises / raised / secures $ / funding / Series A-F / seed round / venture / IPO / bags $
     leadership  appoint* / elevated / promoted / steps down / resigns / "named <role>" / takes charge / new CEO|MD|head ...
                 (but NOT "named Leader/among/top" rankings)
     policy-hard policy / policies / budget / tax / regulation / incentives / cabinet / MeitY / DPDP / scheme / SEZ / STPI / MoU with a state
     expansion   opens / launches / inaugurates / sets up / establish* / expands / new centre|office|campus|hub / leases / sq ft / enters India
     hiring      hiring / hires / jobs / layoffs / job cuts / talent / recruit* / salary / attrition / headcount / workforce / skills / vacancies
     policy-soft government / govt / minister / CM / state-name-led / ministry
     ai          AI / GenAI / agentic / machine learning / automation / LLM
     other       everything else
   Only kind='news' rows are recomputed; analysis/explainer rows keep a category if they already have one.

2) expansions noise cleaning: DELETE a row only when the headline is clearly NOT a launch / expansion / closure
   announcement of a specific company.  Rules are named so the report shows which rule removed what:
     gulf        'GCC' meaning the Gulf Cooperation Council (anti-dumping, dialysis, Dubai Mall, Aramex logistics, Emirates NBD ...)
     listicle    guides, how-to, "Why ...", top-N lists, explainers, editorials ("BS EDIT"), "THE NEXT DECADE", questions
     aggregate   collective subjects: "Over 100 Japanese firms", "German Mittelstand", "PE firms", "IT firms cut jobs", "111 new centres"
     government  state/minister/CM/FM statements and summits (UP targets 500 GCCs, ICAI summit, "T'gana plans") - no specific company
     rumour      "Market Chatter", stock-move items
     hiring-stat generic hiring-statistics items ("AI skills power new GCC hiring")
   Everything else is kept (we err on the side of keeping).

3) relevance (workers/relevance.py): articles.relevant = is_relevant(title); clearly irrelevant rows are DELETED (backup appended to
   workers/data/removed_articles.csv), except rows with comments/votes which are only flagged relevant=false.
4) dedupe: near-identical headlines (same event, different outlet) -> keep the most reputable / earliest, delete the rest (also in expansions).
5) city: single-city mention (incl. aliases + well-known micro-markets like HITEC City / Taramani) fills articles.city and expansions.city.

Run: python workers/classify.py [--dry] [--no-expansions] [--no-clean]     (order: relevance -> dedupe -> city -> category -> expansions)
"""
import os, re, sys, csv, datetime as dt
import psycopg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relevance import is_relevant, why as relevance_why
HERE = os.path.dirname(os.path.abspath(__file__))

DSN = os.environ.get("DATABASE_URL", "postgresql://gcc:gcc@localhost/gcc")
I = re.I
R = lambda p: re.compile(p, I)

RULES = [
    ("funding", R(r"\b(raises?|raised|raising|secures?\s+(?:[$₹€£]|rs\b|usd|inr|\d)|funding (?:round|of|from|boost|to)|series\s+[a-f]\b|seed\s+(?:round|funding)|pre-seed|venture (?:capital|debt)|"
                  r"ipo (?:filing|launch|opens|date)|mops up|unicorn|valuation|closes .{0,30}round|investors? (?:back|pour)|led by .{0,40}(?:capital|ventures|partners))")),
    ("leadership", R(r"\b(appoint\w*|elevated|promoted|steps? down|stepping down|resign\w*|moves on|takes? (?:charge|over as|helm)|new (?:ceo|cto|cio|cfo|coo|md|head|chairman|president|country head)|"
                     r"named\s+(?:as\s+|to\s+|the\s+|new\s+)*(?:ceo|cto|cio|cfo|coo|chief|head|director|md|managing|president|vp|vice|chairman|chair|lead\b|country|global|senior|svp|evp)|"
                     r"to (?:lead|head) (?:the |its |india|new )|joins\b.{0,60}\bas\b|co-?heads?\b|redesignated)")),
    ("policy", R(r"\b(policy|policies|budget|tax(?:es|ation)?|regulat\w+|incentives?|cabinet|meity|dpdp|data protection|scheme|sez|stpi|pli\b|"
                 r"mou with .{0,25}(?:government|govt)|gst\b|transfer pricing|safe harbou?r|union budget|compliance)\b")),
    ("expansion", R(r"\b(open|opens|opened|opening|launch\w*|inaugurat\w+|sets?\s+up|setting up|establish\w*|expand\w*|expansion|new (?:gcc|centre|center|office|campus|hub|facility|lab)|"
                    r"leases?|sq\.? ?ft|square[- ]f\w+|enters? india|to build|picks .{0,30} for|invests?\b.{0,30}(?:crore|cr|million|mn|bn|billion)|relocat\w+|shuts?|closes|closing|winds? down|acquires?|acquisition)\b")),
    ("hiring", R(r"\b(hiring|hires?|hired|jobs?|layoffs?|job cuts?|cuts? jobs|talent|recruit\w*|salar(?:y|ies)|attrition|headcount|workforce|skills?|vacanc\w+|openings|upskill\w*|freshers?|employees|staff(?:ing)?|careers?)\b")),
    ("policy", R(r"\b(government|govt|minister|ministry|chief minister|cm\b|state[- ]led|centre'?s|sitharaman|niti aayog|parliament|lok sabha)\b")),
    ("ai", R(r"(\bai\b|\bgen\s?ai\b|artificial intelligence|agentic|machine learning|\bllms?\b|automation|\bml\b|physical ai|copilot)")),
]
NOT_LEADERSHIP = R(r"named\s+(?:a\s+|as\s+a\s+)?(?:leader|among|in\b|top\b|one of|best|winner|finalist)|named\s+.{0,20}\bleader in\b|leader in\b")
LEADERSHIP_ROLE = R(r"\b(ceo|cto|cio|cfo|coo|chief|head|director|md|managing|president|vp|vice|chairman|chair|lead|country|svp|evp|officer|partner|co-head)\b")
EXP_STRONG = R(r"\b(open|opens|opened|launch\w*|inaugurat\w+|sets?\s+up|establish\w*|expand\w*)\b")


def categorize(title):
    t = title or ""
    for cat, rx in RULES:
        if rx.search(t):
            if cat == "leadership":
                if NOT_LEADERSHIP.search(t) and not re.search(r"appoint\w*|elevated|promoted", t, I): continue
                if not LEADERSHIP_ROLE.search(t) and not re.search(r"appoint\w*|elevated|promoted", t, I): continue
            if cat == "funding" and re.search(r"\bipo\b", t, I) and re.search(r"funding", t, I) is None and not re.search(r"raises?|raised|series", t, I): pass
            return cat
    return "other"


# ---- expansions noise ------------------------------------------------------------------------------------------
NOISE = [
    ("gulf", R(r"anti-dumping|dialysis|wellness cent|dubai mall|flagship store|aramex|emirates nbd|\becm\b|saudi|gulf cooperation|\bgcc (?:states|countries|nations|region|market)|across gcc, asia")),
    ("rumour", R(r"market chatter|stock (?:price|in focus|to watch)|target of rs\b")),
    ("listicle", R(r"complete step-by-step|step-by-step guide|^how to\b|how to set up|\bwhy\b|\bexplained\b|\bguide\b|\btop \d+|^\d+ (?:best|top|reasons|things)|bs edit|editorial|opinion\b|the next decade|"
                   r"latest gcc launches|boom accelerates|should focus|\?$|ranking|ranked|key cities fueling|rise as gcc powerhouse|\bsummit\b|\bforum\b|\bconference\b|\bwebinar\b|\bawards?\b|fellowship|"
                   r"\bsurvey\b|\bstudy\b|\bindex\b|\bplaybook\b")),
    ("aggregate", R(r"^(?:over |more than )?\d[\d,]*\+? (?:japanese|german|us|american|global|new)\b|\b(?:over|more than|\d+\+?) japanese (?:companies|firms)\b|german (?:mid-sized|mittelstand)|\bpe firms\b|\bit firms\b|"
                    r"india.?s gccs (?:cut|expand|add)|\d+ new centres|gcc wave|gcc boom|\bgccs? ecosystem\b|mid-market companies|emerging cities")),
    ("government", R(r"^(?:up|uttar pradesh|t.?gana|telangana|tamil nadu|karnataka|kerala|haryana|odisha|bihar|gujarat|maharashtra|andhra|punjab|rajasthan|state|govt|government|centre|fm|cm|seven|\d+) .{0,40}(?:targets?|plans?|announces?|to set up|pushes|aims|urges|invites)|"
                     r"^(?:cm|fm|samrat choudhary|yogi)\b|\bcm yogi\b|\bsitharaman\b|\bsridhar babu\b|\bit minister\b|invites .{0,20}to (?:establish|set up)|invites .{0,30}\bto set up|"
                     r"announces four new gcc hubs|four global capability centres to be set up in up|haryana.s gcc push|ahmedabad strengthens gcc ambitions|tech park|\bup to set up \d+")),
    ("hiring-stat", R(r"ai(?:,? data)? skills (?:power|now drive)|new gcc roles need|hiring game|65% of new gcc|two[- ]thirds of new gcc|in three new gcc jobs")),
    ("product", R(r"gcc origin|nano gcc|gcc-in-a-box|gcc-as-a-service|as-a-service|business unit|banking vertical|dedicated (?:unit|vertical)|\bcorridor\b|gcc model|gcc offering|gcc services|gcc practice|gcc advisory")),
    ("not-an-announcement", R(r"\bsees\b|\beyes? (?:commercial|entry)|\bsays\b.{0,15}\d+%|\bhow is\b|\bhow will\b|\bimpact\b")),
]
EXP_VERB = R(r"\b(open|opens|opened|opening|launch\w*|inaugurat\w+|sets?\s+up|setting up|establish\w*|expand\w*|to build|leases?|choose[sd]?|picks|signs? mou|shuts?|closes|closing|wind[s]? down|enters?|bets|invests?|to hire|plans? to hire|scale)\b")
CENTRE_NOUN = R(r"gcc|capability cent|tech(?:nology)? cent|engineering cent|innovation cent|global cent|delivery cent|in-house|\bhub\b|technology hub|campus|centre|center")


def noise_rule(title):
    t = title or ""
    for name, rx in NOISE:
        if rx.search(t): return name
    if not is_relevant(t): return "irrelevant"
    if not EXP_VERB.search(t): return "no-launch-verb"
    if not CENTRE_NOUN.search(t): return "no-centre"
    return None


# ---- dedupe ---------------------------------------------------------------------------------------------------
REPUTABLE = ["economic times", "economictimes", "business standard", "the hindu", "livemint", "mint", "moneycontrol", "hindustan times", "indian express", "times of india", "financial express",
             "reuters", "bloomberg", "ndtv profit", "yourstory", "inc42", "nasscom", "people matters", "analytics india", "business today", "the print", "theprint", "deccan herald", "new indian express",
             "telangana today", "cnbc", "techcircle", "express computer", "entrackr", "et cio", "ethrworld", "business wire", "pr newswire"]
GENERIC = set("""a an the in at of to for on and or with as by from its it is are be will new first gcc gccs global capability capabilities centre centres center centers india indian
us uk based firm company major giant opens open opened launches launch launched launching sets set up establishes establish expands expand plans plan announces says report hub office
creates create jobs job hire hiring employees people professionals engineers more over than year years 2025 2026 2027 2028 2029 2030 million crore cr lakh mn bn how what why who which
his her their our new tech technology technologies services service operations operation digital innovation engineering r&d unit arm""".split())
CITY_WORDS = set("bengaluru bangalore hyderabad hyd pune chennai mumbai delhi ncr gurugram gurgaon noida kolkata ahmedabad coimbatore kochi jaipur indore visakhapatnam vizag bhubaneswar lucknow".split())


def norm_title(t):
    t = re.sub(r"\s+[-|–—]\s+[^-|–—]{2,40}$", "", t or "")        # drop trailing " - Publisher"
    t = t.lower().replace("’", "'").replace("&", " and ")
    return re.sub(r"[^a-z0-9₹ ]+", " ", t)


def toks(t):
    return {w for w in norm_title(t).split() if w not in GENERIC and w not in CITY_WORDS and len(w) > 1 and not w.isdigit()}


def rank(source, protected):
    s = (source or "").lower()
    r = next((i for i, k in enumerate(REPUTABLE) if k in s), len(REPUTABLE))
    return (0 if protected else 1, r)


def dedupe_groups(rows, window_days=6, thresh=0.72):
    """rows: [(id, title, source, date, protected)] -> list of (keep_id, [drop_ids]). Union-find on exact normalised title OR token Jaccard >= thresh within window."""
    n = len(rows); parent = list(range(n)); T = [toks(r[1]) for r in rows]; N = [" ".join(norm_title(r[1]).split()) for r in rows]
    def f(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    byn = {}
    for i in range(n):
        if N[i] in byn: parent[f(i)] = f(byn[N[i]])
        else: byn[N[i]] = i
    order = sorted(range(n), key=lambda i: rows[i][3] or dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc))
    for a in range(len(order)):
        i = order[a]
        for b in range(a + 1, len(order)):
            j = order[b]
            di, dj = rows[i][3], rows[j][3]
            if di and dj and (dj - di).days > window_days: break
            if f(i) == f(j) or len(T[i]) < 3 or len(T[j]) < 3: continue
            inter = len(T[i] & T[j]); jac = inter / len(T[i] | T[j])
            if jac >= thresh or (inter >= 4 and inter / min(len(T[i]), len(T[j])) >= 0.85): parent[f(j)] = f(i)
    groups = {}
    for i in range(n): groups.setdefault(f(i), []).append(i)
    out = []
    for g in groups.values():
        if len(g) < 2: continue
        g.sort(key=lambda i: (rank(rows[i][2], rows[i][4]), rows[i][3] or dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc)))
        out.append((rows[g[0]][0], [rows[i][0] for i in g[1:]]))
    return out


# ---- city -------------------------------------------------------------------------------------------------------
CITY_LEX = {
    "Bengaluru": ["bengaluru", "bangalore", "b'luru", "bluru", "electronic city", "whitefield", "manyata", "koramangala", "outer ring road", "devanahalli", "sarjapur"],
    "Hyderabad": ["hyderabad", "hyd", "hitec city", "hi-tec city", "gachibowli", "madhapur", "genome valley", "kokapet", "financial district hyderabad", "telangana's capital"],
    "Pune": ["pune", "hinjewadi", "hinjawadi", "kharadi", "magarpatta", "baner", "ranjangaon"],
    "Chennai": ["chennai", "taramani", "sholinganallur", "dlf downtown", "guindy", "siruseri", "ambattur"],
    "Mumbai": ["mumbai", "navi mumbai", "powai", "bkc", "bandra kurla", "lower parel", "andheri", "thane", "airoli", "mahape"],
    "Gurugram": ["gurugram", "gurgaon", "cyber city", "cyber hub", "udyog vihar"],
    "Noida": ["noida", "greater noida", "sector 62"],
    "Delhi NCR": ["delhi ncr", "delhi-ncr", "new delhi", "delhi", "ncr"],
    "Kolkata": ["kolkata", "calcutta", "salt lake", "rajarhat", "new town kolkata"],
    "Ahmedabad": ["ahmedabad", "gandhinagar", "gift city"],
    "Coimbatore": ["coimbatore"], "Kochi": ["kochi", "cochin", "infopark"], "Jaipur": ["jaipur"], "Indore": ["indore"],
    "Visakhapatnam": ["visakhapatnam", "vizag"], "Bhubaneswar": ["bhubaneswar", "khordha"], "Lucknow": ["lucknow"], "Thiruvananthapuram": ["thiruvananthapuram", "trivandrum", "technopark"],
    "Chandigarh": ["chandigarh", "mohali"], "Nagpur": ["nagpur"], "Mysuru": ["mysuru", "mysore"], "Vadodara": ["vadodara", "baroda"], "Dehradun": ["dehradun"],
}
STATE_HINT = {"telangana": "Hyderabad", "karnataka": "Bengaluru"}
CITY_RX = [(c, re.compile(r"(?<![\w])(?:" + "|".join(re.escape(a) for a in al) + r")(?![\w])", I)) for c, al in CITY_LEX.items()]
NOT_CHENNAI = re.compile(r"chennai corporation|greater chennai", I)


def detect_city(title, category=None):
    t = title or ""
    found = []
    for c, rx in CITY_RX:
        if c == "Chennai" and NOT_CHENNAI.search(t): continue
        m = rx.search(t)
        if m: found.append((m.start(), c))
    # 'Delhi NCR' is a superset hint: drop it when a specific NCR city (Gurugram/Noida) is named
    cities = {c for _, c in found}
    if cities & {"Gurugram", "Noida"}: cities.discard("Delhi NCR")
    if len(cities) == 1: return next(iter(cities))
    if len(cities) > 1: return None                                  # list-type headline ("Bengaluru, Hyderabad and Pune") -> no single city
    if category != "policy":
        for st, c in STATE_HINT.items():
            if re.search(r"\b" + st + r"\b", t, I) and not re.search(r"\b(govt|government|minister|cabinet|policy|state)\b", t, I): return c
    return None


def log(*a): print(*a, flush=True)


def backup_csv(rows):
    path = os.path.join(HERE, "data", "removed_articles.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["removed_at", "id", "reason", "title", "source_name", "source_url", "published_at", "kept_instead_id"])
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for r in rows: w.writerow([now] + list(r))


def main():
    dry = "--dry" in sys.argv
    clean = "--no-clean" not in sys.argv
    conn = psycopg.connect(DSN, autocommit=True)       # autocommit: no transaction is ever held open
    arts = conn.execute("SELECT id,title,source_name,source_url,published_at,kind,category,city,comment_count,score FROM articles ORDER BY id").fetchall()
    exps = conn.execute("SELECT id,company_name,COALESCE(summary,company_name),event,source_url,announced_at,city,company_id FROM expansions ORDER BY id").fetchall()
    n_art0, n_exp0 = len(arts), len(exps)
    removed = []                                             # (id, reason, title, source, url, published, kept)
    drop_ids = set()
    # 1) relevance
    flags = {}
    for a in arts:
        w = relevance_why(a[1]); flags[a[0]] = w.startswith("keep")
        if not flags[a[0]]:
            if (a[8] or 0) > 0 or (a[9] or 0) > 0: continue          # engaged-with rows are only flagged, not deleted
            drop_ids.add(a[0]); removed.append((a[0], w, a[1], a[2], a[3], a[4], ""))
    rel_drop = len(drop_ids)
    reasons = {}
    for r in removed: reasons[r[1]] = reasons.get(r[1], 0) + 1
    log(f"relevance: {n_art0} articles -> drop {rel_drop}  {dict(sorted(reasons.items(), key=lambda x: -x[1]))}")
    # 2) dedupe among survivors
    surv = [a for a in arts if a[0] not in drop_ids]
    dd = dedupe_groups([(a[0], a[1], a[2], a[4], (a[8] or 0) > 0 or (a[9] or 0) > 0) for a in surv])
    byid = {a[0]: a for a in arts}
    for keep, drops in dd:
        for d in drops:
            if (byid[d][8] or 0) > 0 or (byid[d][9] or 0) > 0: continue
            drop_ids.add(d); removed.append((d, "duplicate", byid[d][1], byid[d][2], byid[d][3], byid[d][4], keep))
    log(f"dedupe: {len(dd)} duplicate groups, {len(drop_ids) - rel_drop} duplicates removed")
    # categories + cities for survivors
    upd_cat = []; upd_city = []; dist = {}; city_set = 0
    for a in arts:
        if a[0] in drop_ids: continue
        aid, title, kind, cur_cat, cur_city = a[0], a[1], a[5], a[6], a[7]
        c = categorize(title) if (kind == "news" or not cur_cat) else cur_cat
        dist[c] = dist.get(c, 0) + 1
        if c != cur_cat: upd_cat.append((c, aid))
        newc = detect_city(title, c)
        if newc and newc != cur_city: upd_city.append((newc, aid))
        if newc or cur_city: city_set += 1
    n_after = n_art0 - len(drop_ids)
    log(f"category distribution: {dict(sorted(dist.items(), key=lambda x: -x[1]))}")
    log(f"city: {city_set}/{n_after} articles will have a city ({100 * city_set / max(1, n_after):.0f}%), {len(upd_city)} updates")
    # expansions
    x_drop = []; x_keep = []; src_dead = {a[3] for a in arts if a[0] in drop_ids}
    if "--no-expansions" not in sys.argv:
        for e in exps:
            eid, nm, summ, ev, url, at, city, cid = e
            r = "source-article-removed" if (url in src_dead and not is_relevant(summ)) else noise_rule(summ)
            (x_drop if r else x_keep).append((eid, summ, r, e))
        # near-duplicate events among kept
        ex_rows = [(e[3][0], e[1], None, e[3][5], False) for e in x_keep]
        by_e = {e[0]: e for e in x_keep}
        xd = dedupe_groups(ex_rows, window_days=45, thresh=0.5)
        dup_n = 0
        for keep, drops in xd:
            for d in drops:
                x_drop.append((d, by_e[d][1], "duplicate-event", by_e[d][3])); dup_n += 1
        dead = {x[0] for x in x_drop}
        x_keep = [x for x in x_keep if x[0] not in dead]
        log(f"\nexpansions: before={n_exp0} delete={len(x_drop)} (of which duplicate-event {dup_n}) after={len(x_keep)}")
        by = {}
        for x in x_drop: by[x[2]] = by.get(x[2], 0) + 1
        log("deleted by rule:", dict(sorted(by.items(), key=lambda x: -x[1])))
        import random; random.seed(7)
        log("\n15 sample deletions:")
        for x in random.sample(x_drop, min(15, len(x_drop))): log(f"  #{x[0]} [{x[2]}] {x[1][:105]}")
        log("\n15 kept:")
        for x in random.sample(x_keep, min(15, len(x_keep))): log(f"  #{x[0]} {x[1][:105]}")
        x_city = []
        for x in x_keep:
            e = x[3]
            c2 = detect_city(e[2])
            if c2 and c2 != e[6]: x_city.append((c2, e[0]))
    if dry: return
    if not clean: return
    backup_csv(removed)
    for c, aid in upd_cat: conn.execute("UPDATE articles SET category=%s WHERE id=%s", (c, aid))
    for c, aid in upd_city: conn.execute("UPDATE articles SET city=%s WHERE id=%s", (c, aid))
    conn.execute("UPDATE articles SET relevant = true")
    for aid, ok in flags.items():
        if not ok and aid not in drop_ids: conn.execute("UPDATE articles SET relevant=false WHERE id=%s", (aid,))
    if drop_ids: conn.execute("DELETE FROM articles WHERE id = ANY(%s)", (list(drop_ids),))
    if "--no-expansions" not in sys.argv:
        if x_drop: conn.execute("DELETE FROM expansions WHERE id = ANY(%s)", ([x[0] for x in x_drop],))
        for c, eid in x_city: conn.execute("UPDATE expansions SET city=%s WHERE id=%s", (c, eid))
    log("written; articles now", conn.execute("SELECT count(*) FROM articles").fetchone()[0], "expansions now", conn.execute("SELECT count(*) FROM expansions").fetchone()[0])


if __name__ == "__main__":
    main()
