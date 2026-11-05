#!/usr/bin/env python3
"""The GCC Weekly: builds the weekly digest purely from rows already in the database.

A "week" is Monday 00:00 -> next Monday 00:00 in IST (Asia/Kolkata). Digests are stored in
`digests` (week_start unique) as a full HTML document (email-safe inline styles) plus plain text.
Stored copies contain placeholders that are filled in at read/send time:
    {{SITE}}       -> site origin (the web app swaps it for "" so links stay relative)
    {{UNSUB_URL}}  -> per-subscriber one-click unsubscribe link
    {{PREFS_URL}}  -> subscribe / preferences page

Usage
    python workers/digest.py                    # last completed week: build, store, send (if SMTP set)
    python workers/digest.py --week 2026-10-26  # a specific Monday (build + store; sends only with --send)
    python workers/digest.py --backfill 26      # last 26 completed weeks, never sends
    python workers/digest.py --week 2026-10-26 --send [--force] [--to you@example.com]
    python workers/digest.py --dry-run          # print text, store nothing

Sending (stdlib smtplib, no paid API) needs SMTP_URL (smtp://user:pass@host:587 or smtps://...:465)
or SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS; SMTP_FROM sets the From header. Without SMTP the
run only logs "skipping send".
"""
import argparse, html, json, os, re, smtplib, ssl, sys, time
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

IST = ZoneInfo("Asia/Kolkata")
ISSUE_EPOCH = date(2026, 5, 4)        # issue no. 1 = the first week in the backfill
TOPICS = ["expansions", "leadership", "funding", "policy", "hiring", "ai"]
CAPS = dict(new=8, expanded=6, closed=5, leadership=6, funding=6, policy=5, ai=5, hiring=6, cities=5, reads=8, mine=6)

# --- brand (matches web/app/globals.css) -------------------------------------------------------
PAPER, INK, HOT, LILAC, LIME, MUT = "#f2ede4", "#121212", "#ff4b1f", "#cdbdff", "#d7f25a", "#6b655b"
SERIF = "'Iowan Old Style','Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"

# --- fallback classifier (used only when articles.category is empty) --------------------------
RULES = [
    ("leadership", r"\b(appoints?|appointed|names?|named|elevates?|promoted|steps? down|resigns?|quits|joins as|takes? charge|new (head|chief|ceo|cto|cio|chro)|ceo|cto|cio|chro|vice president|\bvp\b|managing director|country head|site leader)\b"),
    ("funding", r"\b(funding|raises?|raised|series [a-f]\b|invests?|investment|acquires?|acquired|acquisition|stake|ipo|valuation|buys?|merger|crore|deal|joint venture)\b"),
    ("policy", r"\b(polic(y|ies)|minister|government|govt|mou|incentives?|subsid(y|ies)|budget|\bsez\b|tax|regulat\w+|guidelines|framework|cabinet|state-?level|dpiit|meity|stpi)\b"),
    ("expansion", r"\b(opens?|opened|launch(es|ed)?|inaugurates?|inaugurated|expands?|expanded|expansion|sets? up|setting up|new (gcc|centre|center|campus|office|facility|hub)|establish(es|ed)?)\b"),
    ("hiring", r"\b(hiring|hires?|recruit\w*|jobs?|talent|workforce|headcount|layoffs?|attrition|salar(y|ies)|freshers?)\b"),
    ("ai", r"\b(ai|a\.i\.|genai|gen ai|generative|machine learning|llm|agentic|copilot)\b"),
]


def classify(a):
    c = (a.get("category") or "").strip().lower()
    if c and c != "other":
        return {"expansions": "expansion", "jobs": "hiring"}.get(c, c)
    t = (a.get("title") or "").lower()
    for cat, rx in RULES:
        if re.search(rx, t):
            return cat
    return "other"


GULF = re.compile(r"\b(gulf|saudi|uae|emirates|qatar|kuwait|oman|bahrain|dubai|abu dhabi|gcc (ecm|states|countries|markets|region|economies|nations|central bank)|gcc-based)\b", re.I)


def gulf_noise(t):
    """The other GCC (Gulf Cooperation Council): keep it out of the digest unless it is clearly about capability centres."""
    return bool(GULF.search(t or "")) and not re.search(r"capabilit", t or "", re.I)


def clean_title(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    return re.sub(r"\s+[-|–]\s+[^-|–]{2,40}$", "", t)   # strip " - Publisher" suffix from RSS titles


def source_of(a):
    s = a.get("source_name") or ""
    if not s and a.get("source_url"):
        s = urlparse(a["source_url"]).netloc
    return re.sub(r"^https?://|^www\.|/$", "", s)


# --- weeks --------------------------------------------------------------------------------------
def monday_of(d):
    return d - timedelta(days=d.weekday())


def last_completed_monday(now=None):
    today = (now or datetime.now(IST)).date()
    return monday_of(today) - timedelta(days=7)


def bounds(monday):
    s = datetime(monday.year, monday.month, monday.day, tzinfo=IST)
    return s, s + timedelta(days=7)


def issue_no(monday):
    return (monday - ISSUE_EPOCH).days // 7 + 1


def fmt_range(monday):
    sun = monday + timedelta(days=6)
    if monday.month == sun.month:
        return f"{monday.day}–{sun.day} {sun.strftime('%b %Y')}"
    return f"{monday.day} {monday.strftime('%b')} – {sun.day} {sun.strftime('%b %Y')}"


# --- collect ------------------------------------------------------------------------------------
def rows(conn, sql, args):
    return conn.execute(sql, args).fetchall()


def collect(conn, monday):
    s, e = bounds(monday)
    args = (s, e)
    arts = rows(conn, """SELECT id,kind,slug,title,source_name,source_url,city,category,score,comment_count,published_at,
                                (body IS NOT NULL AND body<>'') AS own
                         FROM articles WHERE published_at>=%s AND published_at<%s
                         ORDER BY published_at DESC""", args)
    arts = [a for a in arts if not gulf_noise(a["title"])]
    for a in arts:
        a["cat"] = classify(a)
        a["clean"] = clean_title(a["title"])
        a["url"] = (f"{{{{SITE}}}}/news/{a['slug']}" if a["own"] and a["slug"] else a["source_url"]) or ""
    exps = rows(conn, """SELECT id,company_name,city,event,headcount,summary,source_url,announced_at,verified
                         FROM expansions WHERE announced_at>=%s AND announced_at<%s
                         ORDER BY announced_at DESC""", args)
    exps = [x for x in exps if not gulf_noise(f"{x['company_name']} {x['summary']}")]
    exp_urls = {x["source_url"] for x in exps if x["source_url"]}
    story_n = len(arts)
    arts = [a for a in arts if a["source_url"] not in exp_urls]    # the centres table already carries these
    moves = rows(conn, """SELECT person,role,company_name,city,kind,source_url,published_at FROM people_moves
                          WHERE published_at>=%s AND published_at<%s ORDER BY published_at DESC""", args)
    funds = rows(conn, """SELECT company_name,kind,amount_text,round,investors,summary,source_url,published_at FROM fundings
                          WHERE published_at>=%s AND published_at<%s ORDER BY published_at DESC""", args)
    hiring = rows(conn, """SELECT c.id,c.name,c.parent_company,count(*)::int n,
                                  (array_agg(p.location ORDER BY p.first_seen) FILTER (WHERE p.location IS NOT NULL))[1] loc
                           FROM job_postings p JOIN companies c ON c.id=p.company_id
                           WHERE p.first_seen>=%s AND p.first_seen<%s
                           GROUP BY c.id,c.name,c.parent_company ORDER BY n DESC,c.name LIMIT %s""", (s, e, CAPS["hiring"]))
    new_roles = conn.execute("SELECT count(*)::int n FROM job_postings WHERE first_seen>=%s AND first_seen<%s", args).fetchone()["n"]
    prev_s = s - timedelta(days=7)
    prev = conn.execute("SELECT count(*)::int n FROM articles WHERE published_at>=%s AND published_at<%s", (prev_s, s)).fetchone()["n"]
    return dict(story_n=story_n, arts=arts, exps=exps, moves=moves, funds=funds, hiring=hiring, new_roles=new_roles, prev_stories=prev)


def build_data(conn, monday):
    d = collect(conn, monday)
    arts, exps = d["arts"], d["exps"]
    used = set()           # article ids already placed in a section

    def art_item(a):
        return dict(title=a["clean"], source=source_of(a), url=a["url"], city=a["city"] or "")

    # headline of the week
    headline = None
    ranked = sorted([a for a in arts if (a["score"] or 0) + (a["comment_count"] or 0) > 0],
                    key=lambda a: ((a["score"] or 0) + 2 * (a["comment_count"] or 0), a["published_at"]), reverse=True)
    if ranked:
        a = ranked[0]
        used.add(a["id"])
        headline = dict(art_item(a), why=f"Most discussed on the portal this week: {a['score'] or 0} votes, {a['comment_count'] or 0} comments.")
    elif exps:
        pri = [x for x in exps if x["event"] in ("opened", "expanded", "announced")] or exps
        x = pri[0]
        headline = dict(title=x["summary"] or f"{x['company_name']} {x['event']} in {x['city'] or 'India'}",
                        source=urlparse(x["source_url"]).netloc.replace("www.", "") if x["source_url"] else "GCC Intel tracker",
                        url=x["source_url"] or "", city=x["city"] or "", why="Newest centre on the expansions tracker this week.")
    elif arts:
        a = arts[0]
        used.add(a["id"])
        headline = dict(art_item(a), why="Newest story we tracked this week.")

    def ex_item(x):
        return dict(company=x["company_name"], city=x["city"] or "", headcount=x["headcount"], event=x["event"],
                    summary=(x["summary"] or "")[:200], url=x["source_url"] or "")

    seen_ex = set()

    def uniq(items):
        out = []
        for i in items:
            k = re.sub(r"[^a-z0-9]", "", f"{i['company']}{i['summary']}".lower())[:34]
            k2 = re.sub(r"[^a-z0-9]", "", i["summary"].lower())[:28]
            if k in seen_ex or (k2 and k2 in seen_ex):
                continue
            seen_ex.update({k, k2})
            out.append(i)
        return out

    def ex_item(x, _f=ex_item):
        i = _f(x)
        sm = (x["summary"] or "")
        i["summary"] = sm if len(sm) <= 160 else sm[:160].rsplit(" ", 1)[0] + "\u2026"
        return i

    new = uniq([ex_item(x) for x in exps if x["event"] in ("opened", "announced")])
    expanded = uniq([ex_item(x) for x in exps if x["event"] == "expanded"])
    closed = uniq([ex_item(x) for x in exps if x["event"] == "closed"])

    # leadership: people_moves first, then categorised articles
    leadership = [dict(title=f"{m['person']}, {m['role']}, {m['company_name']}".replace(", None", "").replace(", ,", ","),
                       source=urlparse(m["source_url"]).netloc.replace("www.", "") if m["source_url"] else "",
                       url=m["source_url"] or "", city=m["city"] or "") for m in d["moves"]]
    funding = [dict(title=(f["summary"] or f"{f['company_name']}: {f['amount_text'] or f['kind']}")[:200],
                    source=urlparse(f["source_url"]).netloc.replace("www.", "") if f["source_url"] else "",
                    url=f["source_url"] or "", city="", amount=f["amount_text"] or "") for f in d["funds"]]
    buckets = {"leadership": leadership, "funding": funding, "policy": [], "ai": [], "expansion": [], "hiring": []}
    seen_titles = set()
    for a in arts:
        if a["id"] in used or len(a["clean"]) < 25:
            continue
        if a["cat"] not in buckets:
            continue
        key = a["clean"].lower()[:60]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        if a["cat"] in ("expansion", "hiring"):
            continue       # covered by the centres table / hiring leaderboard; kept for "also read"
        buckets[a["cat"]].append(art_item(a))
        used.add(a["id"])

    # also read: best of the rest, scored then newest
    rest = sorted([a for a in arts if a["id"] not in used],
                  key=lambda a: ((a["score"] or 0) + (a["comment_count"] or 0), a["published_at"]), reverse=True)
    reads, seen = [], set()
    for a in rest:
        if len(a["clean"]) < 25:
            continue
        k = a["clean"].lower()[:60]
        if k in seen:
            continue
        seen.add(k)
        reads.append(dict(art_item(a), cat=a["cat"]))
        if len(reads) >= CAPS["reads"]:
            break

    # own reporting (articles with a body): always worth a mention
    mine = [dict(art_item(a), kind=a["kind"]) for a in arts if a["own"]][: CAPS["mine"]]

    # cities
    cc = {}
    for a in arts:
        if a["city"]:
            cc[a["city"]] = cc.get(a["city"], 0) + 1
    for x in exps:
        if x["city"]:
            cc[x["city"]] = cc.get(x["city"], 0) + 1
    cities = [dict(city=c, n=n) for c, n in sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[: CAPS["cities"]]]

    hiring = [dict(company=h["name"], parent=h["parent_company"] or "", n=h["n"], loc=re.sub(r"(\s*,)+\s*", ", ", h["loc"] or "").strip(", ")) for h in d["hiring"]]
    heads = sum(x["headcount"] or 0 for x in exps if x["event"] in ("opened", "expanded", "announced"))
    numbers = dict(stories=d["story_n"], prev_stories=d["prev_stories"], new_centres=len(new), expanded=len(expanded), closed=len(closed),
                   headcount=heads, new_roles=d["new_roles"], top_city=cities[0]["city"] if cities else "",
                   leadership=len(leadership), funding=len(funding))
    data = dict(week_start=monday.isoformat(), week_end=(monday + timedelta(days=6)).isoformat(), issue=issue_no(monday),
                headline=headline, new=new, expanded=expanded, closed=closed, leadership=leadership, funding=funding,
                policy=buckets["policy"], ai=buckets["ai"], hiring=hiring, cities=cities, reads=reads, mine=mine, numbers=numbers)
    data["city_items"] = [dict(title=f"{x['company']}: {x['summary'] or x['event']}"[:180], url=x["url"], city=x["city"], source="tracker")
                          for x in new + expanded + closed if x["city"]] + \
                         [dict(i, source=i["source"]) for k in ("leadership", "funding", "policy", "ai", "reads") for i in data[k] if i.get("city")]
    return data


def is_empty(data):
    n = data["numbers"]
    return n["stories"] == 0 and not (data["new"] or data["expanded"] or data["closed"] or data["leadership"] or data["funding"])


# --- rendering ----------------------------------------------------------------------------------
esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def lede(data):
    n = data["numbers"]
    bits = [f"{n['stories']} stories tracked" + (f" ({'+' if n['stories'] >= n['prev_stories'] else '-'}{abs(n['stories'] - n['prev_stories'])} on last week)" if n["prev_stories"] else "")]
    if n["new_centres"] or n["expanded"]:
        bits.append(f"{n['new_centres']} new and {n['expanded']} expanded centres on the tracker")
    if n["closed"]:
        bits.append(f"{n['closed']} closure{'s' if n['closed'] != 1 else ''}")
    if n["top_city"]:
        bits.append(f"{n['top_city']} led the city count")
    return "; ".join(bits) + "."


def want(topics, key):
    return not topics or key in topics


def link(url, text, style=""):
    if not url:
        return esc(text)
    return f'<a href="{esc(url)}" style="color:{INK};text-decoration:underline;text-decoration-color:{HOT};text-decoration-thickness:2px;{style}">{esc(text)}</a>'


def label_row(text, color=HOT):
    return (f'<tr><td style="padding:28px 28px 8px 28px;"><div style="font:700 11px {MONO};letter-spacing:.14em;text-transform:uppercase;'
            f'color:{INK};border-bottom:2px solid {INK};padding-bottom:8px;"><span style="color:{color};">&#9632;</span>&nbsp; {esc(text)}</div></td></tr>')


def list_rows(items, meta=lambda i: ""):
    out = []
    for i in items:
        m = meta(i)
        sub = f'<div style="font:12px {MONO};color:{MUT};margin-top:3px;">{esc(m)}</div>' if m else ""
        out.append(f'<tr><td style="padding:9px 28px 0 28px;font:16px/1.4 {SANS};color:{INK};">{link(i.get("url"), i["title"])}{sub}</td></tr>')
    return "".join(out)


def more(total, cap):
    return (f'<tr><td style="padding:8px 28px 0 28px;font:12px {MONO};color:{MUT};">+ {total - cap} more on the site</td></tr>'
            if total > cap else "")


def section(title, items, key, meta=lambda i: "", color=HOT):
    if not items:
        return ""
    cap = CAPS[key]
    return label_row(title, color) + list_rows(items[:cap], meta) + more(len(items), cap)


def centres_rows(items, cap):
    out = []
    for x in items[:cap]:
        hc = f" &middot; {x['headcount']:,} roles" if x.get("headcount") else ""
        loc = esc(x["city"]) if x["city"] else "India"
        note = ""
        if x.get("summary") and x["summary"].lower() != x["company"].lower():
            note = f'<div style="font:14px/1.4 {SANS};color:{MUT};margin-top:2px;">{esc(x["summary"])}</div>'
        out.append(f'<tr><td style="padding:9px 28px 0 28px;font:16px/1.4 {SANS};color:{INK};"><b>{link(x["url"], x["company"])}</b>'
                   f'<span style="font:12px {MONO};color:{MUT};"> &nbsp;{loc}{hc}</span>{note}</td></tr>')
    return "".join(out) + more(len(items), cap)


def render_html(data, topics=None, cities=None):
    topics = [t for t in (topics or []) if t in TOPICS]
    cities = [c for c in (cities or [])]
    n = data["numbers"]
    h = data["headline"]
    parts = []
    # masthead
    parts.append(f'''<tr><td style="background:{INK};padding:22px 28px 20px 28px;">
<div style="font:600 13px {MONO};letter-spacing:.12em;color:{PAPER};text-transform:uppercase;"><span style="color:{HOT};">&#9679;</span>&nbsp; gcc&middot;intel</div>
<div style="font:500 44px/1 {SERIF};color:{PAPER};letter-spacing:-.02em;margin-top:14px;">The GCC <i style="color:{HOT};">Weekly</i></div>
<div style="font:600 12px {MONO};letter-spacing:.1em;color:#a8a296;margin-top:12px;text-transform:uppercase;">No. {data["issue"]} &nbsp;&middot;&nbsp; {esc(fmt_range(date.fromisoformat(data["week_start"])))}</div></td></tr>
<tr><td style="background:{HOT};height:6px;line-height:6px;font-size:0;">&nbsp;</td></tr>
<tr><td style="padding:22px 28px 0 28px;font:18px/1.45 {SERIF};color:{INK};">{esc(lede(data))}</td></tr>''')
    # headline card
    if h:
        parts.append(f'''<tr><td style="padding:22px 28px 0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{LILAC};border:2px solid {INK};border-radius:16px;box-shadow:5px 5px 0 {INK};"><tr><td style="padding:20px 22px;">
<div style="font:700 11px {MONO};letter-spacing:.14em;text-transform:uppercase;color:{INK};">Headline of the week</div>
<div style="font:500 28px/1.12 {SERIF};letter-spacing:-.01em;margin-top:10px;">{link(h["url"], h["title"])}</div>
<div style="font:12px {MONO};color:#3c3730;margin-top:10px;">{esc(h["source"])}{(" &middot; " + esc(h["city"])) if h.get("city") else ""}</div>
<div style="font:14px/1.4 {SANS};color:#3c3730;margin-top:8px;">{esc(h["why"])}</div></td></tr></table></td></tr>''')
    # by the numbers
    cells = [(n["stories"], "stories", "#fff"), (n["new_centres"], "new centres", LIME), (n["expanded"], "expansions", LILAC)]
    cells.append((n["closed"], "closures", "#fff") if n["closed"] or not n["new_roles"] else (f"{n['new_roles']:,}", "new roles seen", "#fff"))
    parts.append(label_row("By the numbers", HOT))
    parts.append('<tr><td style="padding:12px 22px 0 22px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>' +
                 "".join(f'<td width="25%" style="padding:0 6px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{bg};border:2px solid {INK};border-radius:12px;"><tr><td style="padding:12px 8px;text-align:center;">'
                         f'<div style="font:500 30px/1 {SERIF};color:{INK};">{v}</div><div style="font:700 10px {MONO};letter-spacing:.08em;text-transform:uppercase;color:{INK};margin-top:6px;">{esc(lbl)}</div></td></tr></table></td>'
                         for v, lbl, bg in cells) + "</tr></table></td></tr>")
    if n["headcount"]:
        parts.append(f'<tr><td style="padding:10px 28px 0 28px;font:12px {MONO};color:{MUT};">Announced headcount across new and expanded centres: {n["headcount"]:,}.</td></tr>')
    # subscriber's cities
    if cities:
        mine = [i for i in data.get("city_items", []) if i.get("city") in cities][:6]
        if mine:
            parts.append(section("In your cities: " + ", ".join(cities[:3]), mine, "mine", lambda i: i.get("city", ""), LIME))
    # centres
    if want(topics, "expansions"):
        for key, title, col in (("new", "New centres", LIME), ("expanded", "Expanded", LILAC), ("closed", "Closed or scaled down", HOT)):
            if data[key]:
                parts.append(label_row(title, col) + centres_rows(data[key], CAPS[key]))
    if want(topics, "leadership"):
        parts.append(section("Leadership moves", data["leadership"], "leadership", lambda i: i["source"], LILAC))
    if want(topics, "funding"):
        parts.append(section("Funding and deals", data["funding"], "funding", lambda i: " · ".join(x for x in (i.get("amount"), i["source"]) if x), LIME))
    if want(topics, "policy"):
        parts.append(section("Policy watch", data["policy"], "policy", lambda i: i["source"], HOT))
    if want(topics, "ai"):
        parts.append(section("AI in the centres", data["ai"], "ai", lambda i: i["source"], LILAC))
    if want(topics, "hiring") and data["hiring"]:
        parts.append(label_row("Who is hiring", LIME))
        parts.append("".join(f'<tr><td style="padding:9px 28px 0 28px;font:16px/1.4 {SANS};color:{INK};"><b>{esc(x["company"])}</b> '
                             f'<span style="font:12px {MONO};color:{MUT};">&nbsp;{x["n"]} new role{"s" if x["n"] != 1 else ""}{(" &middot; " + esc(x["loc"])) if x["loc"] else ""}</span></td></tr>' for x in data["hiring"]))
    # cities
    if data["cities"]:
        top = data["cities"][0]["n"] or 1
        parts.append(label_row("Top cities this week", LILAC))
        parts.append("".join(f'<tr><td style="padding:8px 28px 0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                             f'<td width="110" style="font:600 14px {SANS};">{esc(c["city"])}</td><td><div style="background:{INK};height:12px;width:{max(6, round(c["n"] / top * 100))}%;border-radius:6px;"></div></td>'
                             f'<td width="40" align="right" style="font:600 12px {MONO};">{c["n"]}</td></tr></table></td></tr>' for c in data["cities"]))
    if data["mine"] and not topics:
        parts.append(section("From the GCC Intel desk", data["mine"], "mine", lambda i: i["kind"], HOT))
    parts.append(section("Also worth reading", data["reads"], "reads", lambda i: " · ".join(x for x in (i["source"], i.get("city")) if x), INK))
    # footer
    parts.append(f'''<tr><td style="padding:34px 28px 8px 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{INK};border-radius:16px;"><tr><td style="padding:20px 22px;">
<div style="font:500 22px/1.1 {SERIF};color:{PAPER};">Read it on the site, search every centre.</div>
<div style="margin-top:14px;"><a href="{{{{SITE}}}}/weekly/{data["week_start"]}" style="display:inline-block;background:{HOT};color:#fff;font:700 14px {SANS};text-decoration:none;padding:10px 20px;border-radius:99px;border:2px solid {PAPER};">Open this issue &rarr;</a></div></td></tr></table></td></tr>
<!--legal-start--><tr><td style="padding:18px 28px 30px 28px;font:12px/1.6 {MONO};color:{MUT};">You get this because you subscribed at gcc·intel. Built each Monday from our own database; every link goes to the original source.<br>
<a href="{{{{PREFS_URL}}}}" style="color:{MUT};">Change topics or cities</a> &nbsp;|&nbsp; <a href="{{{{UNSUB_URL}}}}" style="color:{MUT};">Unsubscribe in one click</a></td></tr><!--legal-end-->''')
    body = "".join(parts)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light">
<title>The GCC Weekly No. {data["issue"]} ({esc(fmt_range(date.fromisoformat(data["week_start"])))})</title></head>
<body style="margin:0;padding:0;background:{PAPER};"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER};"><tr><td align="center" style="padding:20px 10px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:{PAPER};border:2px solid {INK};border-radius:20px;overflow:hidden;">{body}</table>
</td></tr></table></body></html>'''


def render_text(data, topics=None, cities=None):
    topics = [t for t in (topics or []) if t in TOPICS]
    wk = date.fromisoformat(data["week_start"])
    out = [f"THE GCC WEEKLY  No. {data['issue']}  |  {fmt_range(wk)}", "=" * 60, lede(data), ""]
    h = data["headline"]
    if h:
        out += ["HEADLINE OF THE WEEK", h["title"], f"  {h['source']}  {h['url']}", f"  {h['why']}", ""]
    n = data["numbers"]
    out += ["BY THE NUMBERS", f"  {n['stories']} stories | {n['new_centres']} new centres | {n['expanded']} expansions | {n['closed']} closures"
            + (f" | {n['new_roles']:,} new roles" if n["new_roles"] else ""), ""]

    def block(title, items, fmt):
        if items:
            out.extend([title.upper()] + [fmt(i) for i in items] + [""])

    if cities:
        block("In your cities", [i for i in data.get("city_items", []) if i.get("city") in cities][:6], lambda i: f"- {i['title']} ({i['city']})  {i.get('url', '')}")
    if want(topics, "expansions"):
        cen = lambda i: f"- {i['company']}" + (f", {i['city']}" if i["city"] else "") + (f" ({i['headcount']:,} roles)" if i.get("headcount") else "") + (f"  {i['url']}" if i["url"] else "")
        block("New centres", data["new"][:CAPS["new"]], cen)
        block("Expanded", data["expanded"][:CAPS["expanded"]], cen)
        block("Closed or scaled down", data["closed"][:CAPS["closed"]], cen)
    it = lambda i: f"- {i['title']}  {i.get('url', '')}".rstrip()
    if want(topics, "leadership"):
        block("Leadership moves", data["leadership"][:CAPS["leadership"]], it)
    if want(topics, "funding"):
        block("Funding and deals", data["funding"][:CAPS["funding"]], it)
    if want(topics, "policy"):
        block("Policy watch", data["policy"][:CAPS["policy"]], it)
    if want(topics, "ai"):
        block("AI in the centres", data["ai"][:CAPS["ai"]], it)
    if want(topics, "hiring"):
        block("Who is hiring", data["hiring"], lambda x: f"- {x['company']}: {x['n']} new roles" + (f" ({x['loc']})" if x["loc"] else ""))
    block("Top cities", data["cities"], lambda c: f"- {c['city']}: {c['n']}")
    block("Also worth reading", data["reads"], it)
    out += ["-" * 60, f"Open this issue: {{{{SITE}}}}/weekly/{data['week_start']}", "Change topics or cities: {{PREFS_URL}}", "Unsubscribe: {{UNSUB_URL}}"]
    return "\n".join(out)


# --- store ---------------------------------------------------------------------------------------
def store(conn, monday, data):
    title = f"The GCC Weekly No. {data['issue']}: {fmt_range(monday)}"
    html_doc, text = render_html(data), render_text(data)
    r = conn.execute("""INSERT INTO digests(week_start,title,html,text,stats) VALUES(%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (week_start) DO UPDATE SET title=EXCLUDED.title, html=EXCLUDED.html, text=EXCLUDED.text, stats=EXCLUDED.stats
        WHERE digests.sent_at IS NULL RETURNING id""", (monday, title, html_doc, text, json.dumps(data, default=str))).fetchone()
    conn.commit()
    return bool(r)


# --- sending -------------------------------------------------------------------------------------
def smtp_conf():
    url = os.environ.get("SMTP_URL", "").strip()
    c = None
    if url:
        u = urlparse(url)
        c = dict(host=u.hostname, port=u.port or (465 if u.scheme == "smtps" else 587), user=unquote(u.username or ""), pw=unquote(u.password or ""),
                 ssl=u.scheme == "smtps")
    elif os.environ.get("SMTP_HOST"):
        port = int(os.environ.get("SMTP_PORT") or 587)
        c = dict(host=os.environ["SMTP_HOST"], port=port, user=os.environ.get("SMTP_USER", ""), pw=os.environ.get("SMTP_PASS", ""),
                 ssl=os.environ.get("SMTP_SECURE", "").lower() in ("1", "true", "yes") or port == 465)
    if c:
        c["starttls"] = os.environ.get("SMTP_STARTTLS", "1").lower() not in ("0", "false", "no")
        host = c["host"].replace("smtp.", "", 1) if c["host"] else "localhost"
        c["from"] = os.environ.get("SMTP_FROM") or f"The GCC Weekly <digest@{host}>"
    return c


def smtp_open(c):
    ctx = ssl.create_default_context()
    s = smtplib.SMTP_SSL(c["host"], c["port"], context=ctx, timeout=30) if c["ssl"] else smtplib.SMTP(c["host"], c["port"], timeout=30)
    s.ehlo()
    if not c["ssl"] and c["starttls"] and s.has_extn("starttls"):
        s.starttls(context=ctx)
        s.ehlo()
    if c["user"]:
        s.login(c["user"], c["pw"])
    return s


def build_message(c, to, subject, html_doc, text, unsub_url, site):
    m = EmailMessage(policy=policy.SMTP.clone(max_line_length=0))   # long unbreakable List-Unsubscribe URLs must not be RFC2047-encoded
    m["From"], m["To"], m["Subject"] = c["from"], to, subject
    m["Message-ID"] = make_msgid(domain=urlparse(site).hostname or "localhost")
    m["List-Unsubscribe"] = f"<{unsub_url}>"
    m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    m.set_content(text)
    m.add_alternative(html_doc, subtype="html")
    return m


def fill(s, site, unsub, prefs):
    return s.replace("{{SITE}}", site).replace("{{UNSUB_URL}}", unsub).replace("{{PREFS_URL}}", prefs)


def send_digest(conn, monday, force=False, only_to=None):
    c = smtp_conf()
    if not c:
        print("digest: SMTP not configured (SMTP_URL / SMTP_HOST) - skipping send", flush=True)
        return 0
    d = conn.execute("SELECT id,title,stats,sent_at FROM digests WHERE week_start=%s", (monday,)).fetchone()
    if not d:
        print("digest: nothing stored for that week", flush=True)
        return 0
    if d["sent_at"] and not force and not only_to:
        print(f"digest: already sent at {d['sent_at']} (use --force to resend)", flush=True)
        return 0
    site = (os.environ.get("SITE_URL") or "http://localhost:3000").rstrip("/")
    data = d["stats"]
    if only_to:
        subs = [dict(id=0, email=only_to, token="test", topics=[], cities=[])]
    else:
        subs = conn.execute("""SELECT id,email,token,topics,cities FROM subscribers
            WHERE confirmed AND unsubscribed_at IS NULL AND (last_digest IS NULL OR last_digest<%s OR %s) ORDER BY id""", (monday, force)).fetchall()
    if not subs:
        print("digest: no eligible subscribers", flush=True)
        return 0
    sent, srv = 0, None
    delay = 1.0 / max(0.1, float(os.environ.get("SMTP_RATE", "5")))
    for sub in subs:
        try:
            if srv is None:
                srv = smtp_open(c)
            unsub = f"{site}/unsubscribe?token={sub['token']}"
            one_click = f"{site}/unsubscribe/one-click?token={sub['token']}"
            h = fill(render_html(data, sub["topics"], sub["cities"]), site, unsub, f"{site}/subscribe")
            t = fill(render_text(data, sub["topics"], sub["cities"]), site, unsub, f"{site}/subscribe")
            srv.send_message(build_message(c, sub["email"], d["title"], h, t, one_click, site))
            sent += 1
            if sub["id"]:
                conn.execute("UPDATE subscribers SET last_digest=%s WHERE id=%s", (monday, sub["id"]))
                conn.commit()
            time.sleep(delay)
        except (smtplib.SMTPException, OSError) as e:
            print(f"digest: failed for subscriber {sub['id']}: {e}", flush=True)
            try:
                srv and srv.quit()
            except Exception:
                pass
            srv = None
    if srv:
        try:
            srv.quit()
        except Exception:
            pass
    if sent and not only_to:
        conn.execute("UPDATE digests SET sent_at=now(), sent_count=sent_count+%s WHERE id=%s", (sent, d["id"]))
        conn.commit()
    print(f"digest: sent {sent}/{len(subs)}", flush=True)
    return sent


# --- main ----------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", help="Monday (YYYY-MM-DD) of the week to build")
    ap.add_argument("--backfill", type=int, metavar="N", help="build the last N completed weeks (never sends)")
    ap.add_argument("--send", action="store_true", help="send even when --week/--backfill is used")
    ap.add_argument("--force", action="store_true", help="rebuild a sent issue / resend to everyone")
    ap.add_argument("--to", help="send a test copy to this address only")
    ap.add_argument("--dry-run", action="store_true", help="print the plain text, store nothing")
    a = ap.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        if a.backfill:
            last = last_completed_monday()
            made = skipped = 0
            for i in range(a.backfill - 1, -1, -1):
                mon = last - timedelta(days=7 * i)
                data = build_data(conn, mon)
                if is_empty(data):
                    skipped += 1
                    print(f"{mon}: no data, skipped", flush=True)
                    continue
                ok = store(conn, mon, data)
                made += 1 if ok else 0
                n = data["numbers"]
                print(f"{mon}: No.{data['issue']} stories={n['stories']} new={n['new_centres']} exp={n['expanded']} {'stored' if ok else 'kept (already sent)'}", flush=True)
            print(f"backfill done: {made} stored, {skipped} empty weeks skipped")
            return
        if a.week:
            mon = date.fromisoformat(a.week)
            if mon.weekday() != 0:
                sys.exit("--week must be a Monday")
        else:
            mon = last_completed_monday()
        data = build_data(conn, mon)
        if a.dry_run:
            print(render_text(data))
            return
        if is_empty(data) and not a.force:
            print(f"digest {mon}: no data for that week, nothing stored")
            return
        ok = store(conn, mon, data)
        print(f"digest {mon}: {'stored' if ok else 'already sent, kept as is'} ({data['numbers']['stories']} stories)", flush=True)
        if a.to:
            send_digest(conn, mon, only_to=a.to)
        elif a.send or not (a.week or a.backfill):
            send_digest(conn, mon, force=a.force)


if __name__ == "__main__":
    main()
