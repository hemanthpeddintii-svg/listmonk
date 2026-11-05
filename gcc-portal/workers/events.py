"""India GCC events calendar: loads workers/data/events.json into `events` (upsert on name+starts_on).
Only events with a verified date are in the JSON (see its _note for what was excluded and why).
Usage: DATABASE_URL=... python workers/events.py"""
import os, sys, json, datetime as dt, psycopg

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "events.json")


def main():
    rows = json.load(open(PATH))["events"]
    for r in rows:
        if not (r.get("name") and r.get("starts_on") and r.get("source_url")):
            sys.exit(f"refusing to load row without name/starts_on/source_url: {r.get('name')}")
        dt.date.fromisoformat(r["starts_on"])
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO events(name,city,starts_on,ends_on,organiser,url,description,source_url) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(name,starts_on) DO UPDATE SET city=EXCLUDED.city, ends_on=EXCLUDED.ends_on, organiser=EXCLUDED.organiser, "
                "url=EXCLUDED.url, description=EXCLUDED.description, source_url=EXCLUDED.source_url",
                (r["name"], r.get("city"), r["starts_on"], r.get("ends_on"), r.get("organiser"), r.get("url"), r.get("description"), r["source_url"]))
        conn.commit()
    print(f"events loaded: {len(rows)}")


if __name__ == "__main__":
    main()
