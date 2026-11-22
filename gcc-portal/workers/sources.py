"""Pluggable data sources. Implement with licensed/ToS-compliant providers:
 - job_postings: company ATS public JSON (Greenhouse/Lever/Workable boards), or an
   Apify/Apollo job-postings API. Filter to India locations.
 - news_signals: Google News RSS / GDELT for '<company> India GCC expansion' etc.
Stubs below keep the pipeline runnable end-to-end."""
import requests, urllib.parse, xml.etree.ElementTree as ET

def job_postings(name, domain, careers_url):
    """India postings (last ~6 months) from public ATS APIs (Greenhouse, Lever, Ashby,
    SmartRecruiters, Workable). Slugs are cached in workers/data/ats_slugs.json.
    Each dict has title, location, url, department and first_seen (ATS posted/updated date)."""
    from ats_jobs import fetch_company
    try:
        _, posts = fetch_company(name, domain, careers_url)
    except Exception:
        return []
    return [{"title": j["title"], "location": j.get("location"), "url": j["url"],
             "department": j.get("department"), "first_seen": j.get("first_seen")} for j in posts]

def news_signals(name):
    q = urllib.parse.quote(f'"{name}" India GCC OR "capability center"')
    try:
        r = requests.get(f"https://news.google.com/rss/search?q={q}", timeout=15)
        items = ET.fromstring(r.content).iter("item")
        return [{"kind": "news", "headline": i.findtext("title"), "url": i.findtext("link")}
                for _, i in zip(range(5), items)]
    except Exception:
        return []
