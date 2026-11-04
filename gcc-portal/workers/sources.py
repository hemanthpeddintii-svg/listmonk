"""Pluggable data sources. Implement with licensed/ToS-compliant providers:
 - job_postings: company ATS public JSON (Greenhouse/Lever/Workable boards), or an
   Apify/Apollo job-postings API. Filter to India locations.
 - news_signals: Google News RSS / GDELT for '<company> India GCC expansion' etc.
Stubs below keep the pipeline runnable end-to-end."""
import requests, urllib.parse, xml.etree.ElementTree as ET

def job_postings(name, domain, careers_url):
    slug = (domain or "").split(".")[0]
    try:  # Greenhouse public board API
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=15)
        if r.ok:
            return [{"title": j["title"], "location": j["location"]["name"], "url": j["absolute_url"]}
                    for j in r.json().get("jobs", []) if "india" in j["location"]["name"].lower()]
    except Exception:
        pass
    return []

def news_signals(name):
    q = urllib.parse.quote(f'"{name}" India GCC OR "capability center"')
    try:
        r = requests.get(f"https://news.google.com/rss/search?q={q}", timeout=15)
        items = ET.fromstring(r.content).iter("item")
        return [{"kind": "news", "headline": i.findtext("title"), "url": i.findtext("link")}
                for _, i in zip(range(5), items)]
    except Exception:
        return []
