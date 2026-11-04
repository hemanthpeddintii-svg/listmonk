"""Outlet RSS/Atom + site-scoped Google News ingestion -> `articles`.

Stores headline, source, link, date and city ONLY (never article bodies). The feed's own description snippet is used
transiently for the relevance test and is never written to the database.

Relevance filter (transparent, see GCC_PHRASE / GCC_BARE / GULF below):
  * accept: "global capability cent(er|re)", "capability cent(er|re)", "captive (cent(er|re)|unit)" in the headline
    (or, for feed items, the description snippet);
  * accept: bare "GCC"/"GCCs" (case-sensitive) in the headline when there is India context (Indian city/state/Nasscom/crore/...)
    or capability-centre sense words (hiring, talent, leaders, AI, operating model, ...) and no Gulf context;
  * reject: Gulf Cooperation Council items ("GCC countries", Saudi/UAE/Qatar/..., GCC + industrial/logistics/oil/bonds...), and
    "Greater Chennai Corporation" (also abbreviated GCC).
Dedup: source_url (ON CONFLICT DO NOTHING) + normalised-title match (exact, or token-Jaccard >= 0.8 within 5 days)
against everything already in `articles` and against items seen earlier in the same run -> first one kept.

Usage:
  DATABASE_URL=... python workers/sources_rss.py              # daily: all live feeds + last 10 days of site-scoped Google News
  DATABASE_URL=... python workers/sources_rss.py --backfill   # also walk 2026-05-04..today in 14-day windows per outlet
  python workers/sources_rss.py --check                       # re-verify every feed URL, rewrite workers/data/outlets.json
  python workers/sources_rss.py --dry-run ...                 # no DB writes
"""
import os, re, sys, json, time, argparse, datetime as dt, html, urllib.parse, email.utils, concurrent.futures as cf
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from relevance import is_relevant as _is_relevant
OUTLETS_JSON = os.path.join(HERE, "data", "outlets.json")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
      "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"}

# ---------------------------------------------------------------- relevance filter
GCC_PHRASE = re.compile(r"\b(global|offshore|captive|india|innovation|engineering|technology|r&d)?\s*"
                        r"(capability\s+cent(er|re)s?|captive\s+(cent(er|re)s?|units?|operations?)|"
                        r"global\s+in-?house\s+cent(er|re)s?)\b", re.I)
GCC_BARE = re.compile(r"\bGCCs?\b")                      # case-sensitive on purpose (not "gcc" compiler / "Gcc")
INDIA_CTX = re.compile(
    r"\b(india|indian|nasscom|crore|lakh|rs\.?\s?\d|inr|bengaluru|bangalore|hyderabad|pune|chennai|mumbai|delhi|ncr|"
    r"gurugram|gurgaon|noida|kolkata|ahmedabad|gandhinagar|coimbatore|kochi|jaipur|indore|vizag|visakhapatnam|"
    r"thiruvananthapuram|bhubaneswar|lucknow|chandigarh|mohali|nagpur|mysuru|mysore|karnataka|telangana|tamil nadu|"
    r"maharashtra|gujarat|kerala|odisha|andhra|uttar pradesh|rajasthan|madhya pradesh|haryana|punjab|west bengal|"
    r"meity|itbt|tier-?2|offshore|talent|hiring|hire)\b", re.I)
GULF = re.compile(r"gulf cooperation|\bgcc (countries|nations|states|region|markets?|summit|leaders|bloc|members?|"
                  r"central bank)\b|\b(saudi|riyadh|jeddah|uae|dubai|abu dhabi|qatar|doha|kuwait|oman|bahrain|emirates|"
                  r"gulf)\b", re.I)
GULF_SECTOR = re.compile(r"\bGCC\b.{0,40}\b(industrial|logistics|property|real estate|bonds?|sukuk|sovereign|stocks?|equit(y|ies)|"
                         r"economy|banks?|airlines?|telecom|tourism|visa|oil|gas|energy|data cent(er|re)s?|warehous\w*)\b|"
                         r"\b(industrial|logistics|property|real estate|sukuk|sovereign|oil|tourism)\b.{0,40}\bGCC\b", re.I)
GCC_SENSE = re.compile(r"\b(hiring|talent|jobs|leaders?|leadership|cxo|ai|agentic|operating model|ecosystem|workforce|roles?|"
                       r"engineering|innovation|skills?|upskilling|offshore|set(s|ting)? up|expan\w+|head|heads|cio|cto|"
                       r"enterprise|digital|transformation|mandate|maturity|value|scale|capabilit\w+)\b", re.I)
CHENNAI_CORP = re.compile(r"greater chennai|chennai corporation|\bGCC\b.{0,30}\b(commissioner|mayor|school|park|ward|zone|"
                          r"councillor|councillors|corporation)\b", re.I)


def relevant(title, desc=""):
    """Return (ok, why). `desc` is the feed snippet; it may only trigger on the full phrases."""
    t = title or ""
    if GCC_PHRASE.search(t):
        return True, "phrase-title"
    if GCC_BARE.search(t) and not CHENNAI_CORP.search(t):
        if GULF.search(t) or GULF_SECTOR.search(t):
            return False, "gulf"
        if INDIA_CTX.search(t):
            return True, "gcc-india-title"
        if GCC_SENSE.search(t):
            return True, "gcc-capability-sense"
        return False, "gcc-no-india-ctx"
    if desc and GCC_PHRASE.search(desc) and not GULF.search(t + " " + desc[:300]):
        return True, "phrase-desc"
    return False, "no-match"


# ---------------------------------------------------------------- city detection (same lexicon as backfill_news.py)
try:
    from backfill_news import CITIES, CITY_ALIASES
except Exception:  # keeps the module importable stand-alone
    CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi NCR", "Gurugram", "Noida", "Kolkata",
              "Ahmedabad", "Coimbatore", "Kochi", "Jaipur", "Indore", "Visakhapatnam"]
    CITY_ALIASES = {"Gurgaon": "Gurugram", "Bangalore": "Bengaluru", "Vizag": "Visakhapatnam", "Cochin": "Kochi",
                    "Bombay": "Mumbai", "Calcutta": "Kolkata", "Madras": "Chennai"}
EXTRA_CITIES = {"Gandhinagar": "Ahmedabad", "GIFT City": "Ahmedabad", "Thiruvananthapuram": "Thiruvananthapuram",
                "Bhubaneswar": "Bhubaneswar", "Lucknow": "Lucknow", "Chandigarh": "Chandigarh", "Mohali": "Chandigarh",
                "Nagpur": "Nagpur", "Mysuru": "Mysuru", "Mysore": "Mysuru", "Navi Mumbai": "Mumbai", "Delhi": "Delhi NCR",
                "New Delhi": "Delhi NCR", "NCR": "Delhi NCR", "Greater Noida": "Noida"}


def detect_city(title):
    t = title.lower()
    for c in CITIES:
        if re.search(r"\b" + re.escape(c.lower()) + r"\b", t):
            return c
    for alias, c in {**CITY_ALIASES, **EXTRA_CITIES}.items():
        if re.search(r"\b" + re.escape(alias.lower()) + r"\b", t):
            return c
    return None


# ---------------------------------------------------------------- outlet / feed catalogue seed
# (outlet, domain). The domain is used for the site-scoped Google News queries and to sanity check their results.
OUTLETS = [
    ("Economic Times", "economictimes.indiatimes.com"), ("ET CIO", "cio.economictimes.indiatimes.com"),
    ("ETHRWorld", "hr.economictimes.indiatimes.com"), ("Business Standard", "business-standard.com"),
    ("The Hindu BusinessLine", "thehindubusinessline.com"), ("The Hindu", "thehindu.com"),
    ("Mint", "livemint.com"), ("Moneycontrol", "moneycontrol.com"), ("Inc42", "inc42.com"),
    ("YourStory", "yourstory.com"), ("Entrackr", "entrackr.com"), ("Financial Express", "financialexpress.com"),
    ("Hindustan Times", "hindustantimes.com"), ("NDTV Profit", "ndtvprofit.com"), ("Times of India", "timesofindia.indiatimes.com"),
    ("Nasscom", "nasscom.in"), ("Nasscom Community", "community.nasscom.in"), ("HRKatha", "hrkatha.com"),
    ("People Matters", "peoplematters.in"), ("Analytics India Magazine", "analyticsindiamag.com"),
    ("Express Computer", "expresscomputer.in"), ("BW Businessworld", "businessworld.in"),
    ("Indian Express", "indianexpress.com"), ("Telangana Today", "telanganatoday.com"), ("CNBC-TV18", "cnbctv18.com"),
    ("Business Today", "businesstoday.in"), ("CXOToday", "cxotoday.com"), ("Tech Circle", "techcircle.in"),
    ("Deccan Herald", "deccanherald.com"), ("New Indian Express", "newindianexpress.com"), ("ThePrint", "theprint.in"),
    ("Medianama", "medianama.com"), ("Scroll", "scroll.in"), ("Tech in Asia", "techinasia.com"), ("IT Voice", "itvoice.in"),
    ("Firstpost", "firstpost.com"), ("News18", "news18.com"), ("Zee Business", "zeebiz.com"), ("BQ Prime", "bqprime.com"),
    ("Outlook Business", "outlookbusiness.com"), ("India Today", "indiatoday.in"), ("IndianWeb2", "indianweb2.com"),
    ("Tech Observer", "techobserver.in"), ("DQ India", "dqindia.com"), ("Siliconindia", "siliconindia.com"),
    ("The Hans India", "thehansindia.com"), ("PIB", "pib.gov.in"), ("CIOL", "ciol.com"), ("Fortune India", "fortuneindia.com"),
    ("The Week", "theweek.in"), ("The Tribune", "tribuneindia.com"), ("Mathrubhumi", "mathrubhumi.com"),
    ("Odisha TV", "odishatv.in"), ("Free Press Journal", "freepressjournal.com"), ("Dataquest", "dqindia.com"),
    ("Ahmedabad Mirror", "ahmedabadmirror.com"), ("Economic Times Realty", "realty.economictimes.indiatimes.com"),
    ("Business Line Tamil Nadu", "thehindubusinessline.com"),
]
OUTLETS = list(dict.fromkeys(OUTLETS))
ET_ = "https://economictimes.indiatimes.com"
TOI = "https://timesofindia.indiatimes.com/rssfeeds"
HIND = "https://www.thehindu.com/news/cities"
# (outlet, feed name, url, default_city). default_city is only a fallback when the headline has no city.
FEEDS = [
    ("Economic Times", "ET Tech", ET_ + "/tech/rssfeeds/13357270.cms", None),
    ("Economic Times", "ET Information Tech", ET_ + "/tech/information-tech/rssfeeds/13357555.cms", None),
    ("Economic Times", "ET Industry", ET_ + "/industry/rssfeeds/13352306.cms", None),
    ("Economic Times", "ET Jobs", ET_ + "/jobs/rssfeeds/107115.cms", None),
    ("Economic Times", "ET Top Stories", ET_ + "/rssfeedstopstories.cms", None),
    ("Economic Times", "ET Company", ET_ + "/news/company/rssfeeds/2143429.cms", None),
    ("Economic Times", "ET Startups", ET_ + "/small-biz/startups/rssfeeds/11993050.cms", None),
    ("Economic Times", "ET Banking & Finance", ET_ + "/industry/banking/finance/rssfeeds/13358259.cms", None),
    ("Economic Times", "ET Markets", ET_ + "/markets/rssfeeds/1977021501.cms", None),
    ("ET CIO", "ETCIO Top Stories", "https://cio.economictimes.indiatimes.com/rss/topstories", None),
    ("ET CIO", "ETCIO Recent Stories", "https://cio.economictimes.indiatimes.com/rss/recentstories", None),
    ("ETHRWorld", "ETHRWorld Top Stories", "https://hr.economictimes.indiatimes.com/rss/topstories", None),
    ("ETHRWorld", "ETHRWorld Recent Stories", "https://hr.economictimes.indiatimes.com/rss/recentstories", None),
    ("Economic Times Realty", "ET Realty Top Stories", "https://realty.economictimes.indiatimes.com/rss/topstories", None),
    ("Business Standard", "BS Companies", "https://www.business-standard.com/rss/companies-101.rss", None),
    ("Business Standard", "BS Technology", "https://www.business-standard.com/rss/technology-108.rss", None),
    ("Business Standard", "BS Economy", "https://www.business-standard.com/rss/economy-102.rss", None),
    ("Business Standard", "BS Industry", "https://www.business-standard.com/rss/industry-217.rss", None),
    ("Business Standard", "BS Top Stories", "https://www.business-standard.com/rss/home_page_top_stories.rss", None),
    ("Business Standard", "BS Finance", "https://www.business-standard.com/rss/finance-103.rss", None),
    ("The Hindu BusinessLine", "BL Companies", "https://www.thehindubusinessline.com/companies/feeder/default.rss", None),
    ("The Hindu BusinessLine", "BL Info-tech", "https://www.thehindubusinessline.com/info-tech/feeder/default.rss", None),
    ("The Hindu BusinessLine", "BL Economy", "https://www.thehindubusinessline.com/economy/feeder/default.rss", None),
    ("The Hindu BusinessLine", "BL News", "https://www.thehindubusinessline.com/news/feeder/default.rss", None),
    ("The Hindu BusinessLine", "BL Markets", "https://www.thehindubusinessline.com/markets/feeder/default.rss", None),
    ("The Hindu", "Hindu Business", "https://www.thehindu.com/business/feeder/default.rss", None),
    ("The Hindu", "Hindu Technology", "https://www.thehindu.com/sci-tech/technology/feeder/default.rss", None),
    ("The Hindu", "Hindu Bengaluru", HIND + "/bangalore/feeder/default.rss", "Bengaluru"),
    ("The Hindu", "Hindu Hyderabad", HIND + "/Hyderabad/feeder/default.rss", "Hyderabad"),
    ("The Hindu", "Hindu Chennai", HIND + "/chennai/feeder/default.rss", "Chennai"),
    ("The Hindu", "Hindu Coimbatore", HIND + "/Coimbatore/feeder/default.rss", "Coimbatore"),
    ("The Hindu", "Hindu Kochi", HIND + "/Kochi/feeder/default.rss", "Kochi"),
    ("The Hindu", "Hindu Visakhapatnam", HIND + "/Visakhapatnam/feeder/default.rss", "Visakhapatnam"),
    ("The Hindu", "Hindu Mumbai", HIND + "/Mumbai/feeder/default.rss", "Mumbai"),
    ("The Hindu", "Hindu Delhi", HIND + "/Delhi/feeder/default.rss", "Delhi NCR"),
    ("Mint", "Mint Companies", "https://www.livemint.com/rss/companies", None),
    ("Mint", "Mint Technology", "https://www.livemint.com/rss/technology", None),
    ("Mint", "Mint Industry", "https://www.livemint.com/rss/industry", None),
    ("Mint", "Mint News", "https://www.livemint.com/rss/news", None),
    ("Mint", "Mint Money", "https://www.livemint.com/rss/money", None),
    ("Inc42", "Inc42 main", "https://inc42.com/feed/", None),
    ("YourStory", "YourStory main", "https://yourstory.com/feed", None),
    ("Hindustan Times", "HT Business", "https://www.hindustantimes.com/feeds/rss/business/rssfeed.xml", None),
    ("Hindustan Times", "HT India", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", None),
    ("Hindustan Times", "HT Technology", "https://www.hindustantimes.com/feeds/rss/technology/rssfeed.xml", None),
    ("Hindustan Times", "HT Bengaluru", "https://www.hindustantimes.com/feeds/rss/cities/bengaluru-news/rssfeed.xml", "Bengaluru"),
    ("NDTV Profit", "NDTV Profit latest (feedburner)", "https://feeds.feedburner.com/ndtvprofit-latest", None),
    ("Times of India", "TOI Business", TOI + "/1898055.cms", None),
    ("Times of India", "TOI Bengaluru", TOI + "/-2128833038.cms", "Bengaluru"),
    ("Times of India", "TOI Hyderabad", TOI + "/-2128816011.cms", "Hyderabad"),
    ("Times of India", "TOI Chennai", TOI + "/2950623.cms", "Chennai"),
    ("Times of India", "TOI Pune", TOI + "/-2128821153.cms", "Pune"),
    ("Times of India", "TOI Mumbai", TOI + "/-2128838597.cms", "Mumbai"),
    ("Times of India", "TOI Delhi", TOI + "/-2128839596.cms", "Delhi NCR"),
    ("Times of India", "TOI Kolkata", TOI + "/-2128830821.cms", "Kolkata"),
    ("Times of India", "TOI Gurgaon", TOI + "/6547154.cms", "Gurugram"),
    ("Times of India", "TOI Jaipur", TOI + "/3012544.cms", "Jaipur"),
    ("Times of India", "TOI Indore", TOI + "/3012535.cms", "Indore"),
    ("Times of India", "TOI Kochi", TOI + "/878156991.cms", "Kochi"),
    ("HRKatha", "HRKatha main", "https://www.hrkatha.com/feed/", None),
    ("HRKatha", "HRKatha tag GCC", "https://www.hrkatha.com/tag/gcc/feed/", None),
    ("HRKatha", "HRKatha search GCC", "https://hrkatha.com/?s=GCC&feed=rss2", None),
    ("HRKatha", "HRKatha search capability centre", "https://hrkatha.com/?s=capability+centre&feed=rss2", None),
    ("Analytics India Magazine", "AIM main", "https://analyticsindiamag.com/feed/", None),
    ("Analytics India Magazine", "AIM tag GCC", "https://analyticsindiamag.com/tag/gcc/feed/", None),
    ("Express Computer", "Express Computer main", "https://www.expresscomputer.in/feed/", None),
    ("Express Computer", "Express Computer search GCC", "https://www.expresscomputer.in/?s=GCC&feed=rss2", None),
    ("Indian Express", "IE Business", "https://indianexpress.com/section/business/feed/", None),
    ("Indian Express", "IE Technology", "https://indianexpress.com/section/technology/feed/", None),
    ("Indian Express", "IE Economy", "https://indianexpress.com/section/business/economy/feed/", None),
    ("Indian Express", "IE Jobs", "https://indianexpress.com/section/jobs/feed/", None),
    ("Indian Express", "IE Bangalore", "https://indianexpress.com/section/cities/bangalore/feed/", "Bengaluru"),
    ("Indian Express", "IE Hyderabad", "https://indianexpress.com/section/cities/hyderabad/feed/", "Hyderabad"),
    ("Indian Express", "IE Pune", "https://indianexpress.com/section/cities/pune/feed/", "Pune"),
    ("Indian Express", "IE Chennai", "https://indianexpress.com/section/cities/chennai/feed/", "Chennai"),
    ("Telangana Today", "Telangana Today main", "https://telanganatoday.com/feed", "Hyderabad"),
    ("Telangana Today", "Telangana Today business", "https://telanganatoday.com/category/business/feed", "Hyderabad"),
    ("CNBC-TV18", "CNBC-TV18 latest", "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/latest.xml", None),
    ("CNBC-TV18", "CNBC-TV18 business", "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/business.xml", None),
    ("Business Today", "Business Today latest", "https://www.businesstoday.in/rss/latest", None),
    ("Business Today", "Business Today industry", "https://www.businesstoday.in/rssfeeds/?id=225346", None),
    ("CXOToday", "CXOToday search GCC", "https://www.cxotoday.com/?s=GCC&feed=rss2", None),
    ("Medianama", "Medianama main", "https://www.medianama.com/feed/", None),
    ("ThePrint", "ThePrint economy", "https://theprint.in/category/economy/feed/", None),
    ("Scroll", "Scroll (feedburner)", "https://feeds.feedburner.com/ScrollinArticles.rss", None),
    ("Tech in Asia", "Tech in Asia main", "https://www.techinasia.com/feed", None),
    ("IT Voice", "IT Voice main", "https://itvoice.in/feed", None),
    ("India Today", "India Today business", "https://www.indiatoday.in/rss/1206513", None),
    ("IndianWeb2", "IndianWeb2 main", "https://www.indianweb2.com/feeds/posts/default", None),
    ("Tech Observer", "Tech Observer main", "https://techobserver.in/feed/", None),
    ("The Hans India", "Hans India business", "https://www.thehansindia.com/rss/business", None),
    ("PIB", "PIB (Ministry feed)", "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", None),
    # known-dead / blocked as of 2026-11-04 (kept so --check can re-test them; they are covered via Google News)
    ("Moneycontrol", "Moneycontrol business", "https://www.moneycontrol.com/rss/business.xml", None),
    ("Moneycontrol", "Moneycontrol latest", "https://www.moneycontrol.com/rss/latestnews.xml", None),
    ("Entrackr", "Entrackr main", "https://entrackr.com/feed", None),
    ("Financial Express", "FE industry", "https://www.financialexpress.com/industry/feed/", None),
    ("Financial Express", "FE jobs", "https://www.financialexpress.com/jobs-career/feed/", None),
    ("NDTV Profit", "NDTV Profit rss", "https://www.ndtvprofit.com/rss/feeds", None),
    ("Nasscom", "Nasscom feed", "https://nasscom.in/feed", None),
    ("Nasscom Community", "Nasscom Community rss", "https://community.nasscom.in/rss.xml", None),
    ("People Matters", "People Matters rss", "https://www.peoplematters.in/rss", None),
    ("BW Businessworld", "BW rss", "https://www.businessworld.in/rss/all", None),
    ("New Indian Express", "NIE business", "https://www.newindianexpress.com/Business/rssfeed/?id=170&getXmlFeed=true", None),
    ("Deccan Herald", "DH business", "https://www.deccanherald.com/rss/business.rss", None),
    ("CXOToday", "CXOToday main", "https://www.cxotoday.com/feed/", None),
    ("Tech Circle", "Tech Circle rss", "https://www.techcircle.in/rss", None),
    ("ThePrint", "ThePrint main", "https://theprint.in/feed/", None),
    ("Firstpost", "Firstpost business", "https://www.firstpost.com/commonfeeds/v1/mfp/rss/business.xml", None),
    ("News18", "News18 business", "https://www.news18.com/commonfeeds/v1/eng/rss/business.xml", None),
    ("Zee Business", "Zee Business companies", "https://www.zeebiz.com/companies.xml", None),
    ("BQ Prime", "BQ Prime rss", "https://www.bqprime.com/rss", None),
    ("Outlook Business", "Outlook Business feed", "https://www.outlookbusiness.com/feed", None),
    ("DQ India", "DQ India feed", "https://www.dqindia.com/feed/", None),
    ("Siliconindia", "Siliconindia news", "https://www.siliconindia.com/rss/news", None),
    ("Free Press Journal", "FPJ business", "https://www.freepressjournal.com/rss/business", None),
    ("Karnataka IT/BT dept", "Karnataka ITBT rss", "https://itbt.karnataka.gov.in/rss", None),
]
FEED_DOMAINS = dict(OUTLETS)

# ---------------------------------------------------------------- helpers
def norm_title(t):
    t = html.unescape(t or "").lower()
    t = re.sub(r"\s+[-|–—:]\s+[^-|–—:]{2,40}$", "", t)           # strip trailing " - Outlet"
    t = re.sub(r"[^a-z0-9 ]+", " ", t.replace("’", "").replace("'", ""))
    return re.sub(r"\s+", " ", t).strip()


STOP = set("the a an of in to for and on at with by from as is are its it new will after says say gcc gcc's gccs".split())


def tokens(nt):
    return frozenset(w for w in nt.split() if w not in STOP and len(w) > 2)


class TitleIndex:
    """Exact + near-duplicate title matcher (token Jaccard >= 0.8, dates within 5 days when both known)."""
    def __init__(self):
        self.exact, self.inv, self.items = {}, defaultdict(list), []

    def add(self, title, at):
        nt = norm_title(title)
        if not nt:
            return
        self.exact.setdefault(nt, at)
        tk = tokens(nt)
        i = len(self.items); self.items.append((tk, at))
        for w in tk:
            if len(w) >= 5:
                self.inv[w].append(i)

    def dup(self, title, at):
        nt = norm_title(title)
        if nt in self.exact:
            return True
        tk = tokens(nt)
        if len(tk) < 4:
            return False
        cand = Counter()
        for w in tk:
            if len(w) >= 5:
                for i in self.inv.get(w, ()):
                    cand[i] += 1
        for i, c in cand.items():
            if c < 3:
                continue
            otk, oat = self.items[i]
            j = len(tk & otk) / max(1, len(tk | otk))
            if j >= 0.8 and (not at or not oat or abs((at - oat).total_seconds()) <= 5 * 86400):
                return True
        return False


def parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or ""))).strip()


def get(url, tries=2, timeout=25):
    last = None
    for a in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            return r
        except Exception as e:
            last = e; time.sleep(1.5 * (a + 1))
    raise last


ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(content):
    """-> list of dict(title,url,at,desc). Handles RSS 2.0 and Atom."""
    root = ET.fromstring(content)
    out = []
    for it in root.iter("item"):
        out.append(dict(title=(it.findtext("title") or "").strip(), url=(it.findtext("link") or "").strip(),
                        at=parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                        desc=strip_tags(it.findtext("description") or "")[:400]))
    for it in root.iter(ATOM + "entry"):
        link = ""
        for l in it.findall(ATOM + "link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
        out.append(dict(title=(it.findtext(ATOM + "title") or "").strip(), url=link,
                        at=parse_date(it.findtext(ATOM + "published") or it.findtext(ATOM + "updated")),
                        desc=strip_tags(it.findtext(ATOM + "summary") or "")[:400]))
    return out


def clean_url(u):
    """Drop tracking params so the same article is not stored twice."""
    p = urllib.parse.urlsplit(u)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ""))


def fetch_feed(feed):
    outlet, name, url, city = feed
    try:
        r = get(url)
        if r.status_code != 200:
            return feed, "failed", r.status_code, []
        items = parse_feed(r.content)
        if not items:
            return feed, "failed", r.status_code, []
        return feed, "ok", r.status_code, items
    except ET.ParseError:
        return feed, "failed", 200, []
    except Exception as e:
        return feed, "failed", 0, []


_CACHE = {}
_CACHE_PATH = os.environ.get("SOURCES_CACHE")      # optional: raw Google News results, so filter tweaks need no refetch
if _CACHE_PATH and os.path.exists(_CACHE_PATH):
    try:
        _CACHE = json.load(open(_CACHE_PATH))
    except Exception:
        _CACHE = {}


def gnews(domain, a, b, sleep=1.0):
    key = f"{domain}|{a}|{b}"
    if key in _CACHE:
        return [dict(i, at=parse_date(i["at"])) for i in _CACHE[key]]
    out = _gnews(domain, a, b, sleep)
    if out is not None and _CACHE_PATH:
        _CACHE[key] = [dict(i, at=i["at"].isoformat() if i["at"] else None) for i in out]
        if len(_CACHE) % 20 == 0:
            json.dump(_CACHE, open(_CACHE_PATH, "w"))
    return out


def _gnews(domain, a, b, sleep=1.0):
    q = f'site:{domain} ("global capability" OR "capability centre" OR "capability center" OR GCC OR "captive centre") after:{a:%Y-%m-%d} before:{b:%Y-%m-%d}'
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-IN&gl=IN&ceid=IN:en"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=25)
            if r.status_code == 200:
                out = []
                for it in ET.fromstring(r.content).iter("item"):
                    src = it.find("source")
                    source = src.text.strip() if src is not None and src.text else None
                    surl = src.get("url", "") if src is not None else ""
                    title = html.unescape((it.findtext("title") or "")).strip()
                    if source and title.endswith(" - " + source):
                        title = title[: -len(source) - 3].strip()
                    out.append(dict(title=title, url=(it.findtext("link") or "").strip(), source=source, surl=surl,
                                    at=parse_date(it.findtext("pubDate")), desc=""))
                time.sleep(sleep)
                return out
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    print(f"  ! google news failed: {domain} {a}..{b}", flush=True)
    return None


def windows(start, end, days):
    d = start
    while d < end:
        e = min(d + dt.timedelta(days=days), end)
        yield d, e
        d = e


def load_catalogue():
    try:
        with open(OUTLETS_JSON) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="walk --start..--end in 14-day windows per outlet via Google News")
    ap.add_argument("--start", default="2026-05-04")
    ap.add_argument("--end", default=None, help="exclusive upper bound; default tomorrow")
    ap.add_argument("--recent-days", type=int, default=10, help="Google News window for the daily run")
    ap.add_argument("--check", action="store_true", help="only re-verify feed URLs and rewrite outlets.json")
    ap.add_argument("--no-gnews", action="store_true")
    ap.add_argument("--all-gnews", action="store_true", help="daily run: query every outlet via Google News, not just feed-less ones")
    ap.add_argument("--no-feeds", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    today = dt.datetime.now(dt.timezone.utc).date()
    end = dt.date.fromisoformat(args.end) if args.end else today + dt.timedelta(days=1)
    stats_feed = {}            # feed name -> dict(status, http, items, relevant, inserted)
    per_outlet, per_month, inserted_rows = Counter(), Counter(), []

    # ---- 1. feeds ---------------------------------------------------------------------------------
    cat = load_catalogue()
    known = {f["url"]: f for f in cat.get("feeds", [])}
    if args.check or args.backfill:             # --check / --backfill re-test everything so the catalogue self-heals
        todo = list(FEEDS)
    else:                                       # daily run: skip feeds the catalogue marks dead
        todo = [f for f in FEEDS if known.get(f[2], {}).get("status", "ok") != "failed"]
    if args.no_feeds:
        todo = []
    results = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(fetch_feed, todo):
            results.append(res)
    cand = []                                   # (outlet, source_name, item, city_hint)
    for (outlet, name, url, city), status, http, items in results:
        rel = 0
        for it in items:
            if not it["title"] or not it["url"]:
                continue
            ok, why = relevant(it["title"], it["desc"])
            if ok:
                rel += 1
                cand.append((outlet, outlet, dict(it, why=why), city))
        stats_feed[url] = dict(outlet=outlet, name=name, url=url, status=status, http=http, items=len(items), relevant=rel,
                               checked=today.isoformat(), default_city=city)

    # ---- 2. Google News site-scoped ------------------------------------------------------------------
    gstats = {}
    if not (args.no_gnews or args.check):
        doms = sorted({d for _, d in OUTLETS})
        if not args.backfill and not args.all_gnews:
            # daily run: only outlets with no working direct feed need Google News (keeps the run to a few minutes)
            live = {o for o, _, u, _ in FEEDS if stats_feed.get(u, {}).get("status") == "ok"}
            doms = sorted({d for o, d in OUTLETS if o not in live})
        if args.backfill:
            wins = list(windows(dt.date.fromisoformat(args.start), end, 14))
        else:
            wins = [(today - dt.timedelta(days=args.recent_days), end)]
        jobs = [(d, a, b) for d in doms for a, b in wins]
        print(f"google news: {len(jobs)} site-scoped requests", flush=True)
        lo = dt.datetime.combine(wins[0][0], dt.time.min, dt.timezone.utc)
        hi = dt.datetime.combine(end, dt.time.min, dt.timezone.utc)

        def work(job):
            return job, gnews(*job)
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            for n, (job, items) in enumerate(ex.map(work, jobs), 1):
                d = job[0]
                g = gstats.setdefault(d, dict(domain=d, requests=0, failed=0, items=0, relevant=0))
                g["requests"] += 1
                if items is None:
                    g["failed"] += 1; continue
                g["items"] += len(items)
                for it in items:
                    if not it["title"] or not it["url"] or not it["at"] or not (lo <= it["at"] < hi):
                        continue
                    sd = urllib.parse.urlsplit(it["surl"]).netloc.lower().removeprefix("www.") if it["surl"] else ""
                    root = ".".join(d.split(".")[-2:]) if not d.endswith(".in") else ".".join(d.split(".")[-2:])
                    if sd and root not in sd and d not in sd:   # Google returned another publisher: ignore
                        continue
                    ok, why = relevant(it["title"])
                    if ok:
                        g["relevant"] += 1
                        outlet = next((o for o, dd in OUTLETS if dd == d), it["source"])
                        cand.append((outlet, it["source"] or outlet, dict(it, why="gnews+" + why), None))
                if n % 50 == 0:
                    print(f"  [{n}/{len(jobs)}]", flush=True)

    # ---- 3. dedupe + insert ---------------------------------------------------------------------------
    if args.check:
        cand = []
    ins = 0
    conn = None
    if not args.dry_run and cand:
        import psycopg
        conn = psycopg.connect(os.environ["DATABASE_URL"])
    idx = TitleIndex()
    names = []
    if conn:
        for t, at in conn.execute("SELECT title, published_at FROM articles"):
            idx.add(t, at)
        names = conn.execute("SELECT id,parent_company FROM companies WHERE parent_company IS NOT NULL").fetchall()
        urls = {r[0] for r in conn.execute("SELECT source_url FROM articles WHERE source_url IS NOT NULL")}
    else:
        urls = set()
    try:
        from backfill_news import sector_tags
    except Exception:
        sector_tags = lambda t: []
    # direct publisher feeds first (canonical URLs), then Google News fallbacks
    cand.sort(key=lambda c: (c[2]["why"].startswith("gnews"), -(c[2]["at"].timestamp() if c[2]["at"] else 0)))
    skipped_dup = 0
    for outlet, source, it, city_hint in cand:
        url = clean_url(it["url"])
        at = it["at"] or dt.datetime.now(dt.timezone.utc)
        if url in urls or idx.dup(it["title"], at):
            skipped_dup += 1; continue
        title = html.unescape(it["title"]).strip()
        if not _is_relevant(title): continue  # enrich agent: shared relevance gate (workers/relevance.py)
        city = detect_city(title) or city_hint
        cid = next((i for i, par in names if par.lower() in title.lower()), None) if names else None
        if conn:
            row = conn.execute(
                "INSERT INTO articles(kind,title,source_name,source_url,city,company_id,tags,published_at) "
                "VALUES('news',%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_url) DO NOTHING RETURNING id",
                (title, source, url, city, cid, sector_tags(title), at)).fetchone()
            if not row:
                skipped_dup += 1; continue
        urls.add(url); idx.add(title, at)
        ins += 1
        per_outlet[outlet] += 1
        per_month[at.strftime("%Y-%m")] += 1
        inserted_rows.append((outlet, at.date().isoformat(), city, title, url))
        if conn and ins % 50 == 0:
            conn.commit()
    if conn:
        conn.commit(); conn.close()

    # ---- 4. catalogue -----------------------------------------------------------------------------------
    feeds_out = []
    for outlet, name, url, city in FEEDS:
        s = stats_feed.get(url) or known.get(url) or dict(outlet=outlet, name=name, url=url, status="unchecked", http=None,
                                                         items=0, relevant=0, checked=None, default_city=city)
        s = dict(s)
        feeds_out.append(s)
    by_outlet = defaultdict(lambda: dict(feeds_ok=0, feeds_failed=0))
    for s in feeds_out:
        by_outlet[s["outlet"]]["feeds_ok" if s["status"] == "ok" else "feeds_failed"] += 1
    outlets_out = []
    for o, d in OUTLETS:
        b = by_outlet.get(o, dict(feeds_ok=0, feeds_failed=0))
        g = gstats.get(d) or (cat.get("google_news", {}) or {}).get(d, {})
        outlets_out.append(dict(name=o, domain=d, feeds_ok=b["feeds_ok"], feeds_failed=b["feeds_failed"],
                                coverage=("rss" if b["feeds_ok"] else "google-news-only"),
                                google_news_items=g.get("items"), google_news_relevant=g.get("relevant")))
    if not args.dry_run and (args.check or results):
        cat_out = dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       note="status=ok means HTTP 200 with >=1 parseable item when last checked. 'google-news-only' outlets have no "
                            "working public feed and are reached via site-scoped Google News RSS queries.",
                       outlets=outlets_out, feeds=feeds_out,
                       google_news={**(cat.get("google_news") or {}), **gstats})
        with open(OUTLETS_JSON, "w") as f:
            json.dump(cat_out, f, indent=1, ensure_ascii=False)

    ok = sum(1 for s in stats_feed.values() if s["status"] == "ok")
    print(f"feeds fetched: {len(stats_feed)} (ok {ok}, failed {len(stats_feed) - ok}); relevant candidates: {len(cand)}; "
          f"duplicates skipped: {skipped_dup}; INSERTED: {ins}")
    print("per outlet:", dict(per_outlet.most_common()))
    print("per month:", dict(sorted(per_month.items())))
    if _CACHE_PATH:
        json.dump(_CACHE, open(_CACHE_PATH, "w"))
    if os.environ.get("SOURCES_DUMP"):
        with open(os.environ["SOURCES_DUMP"], "w") as f:
            json.dump(inserted_rows, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
