import { q } from "./db";
const HUB = { Gurugram: "Delhi NCR", Gurgaon: "Delhi NCR", Noida: "Delhi NCR", Delhi: "Delhi NCR", "New Delhi": "Delhi NCR", Bangalore: "Bengaluru", Vizag: "Visakhapatnam" };
export const hub = (c) => (c ? HUB[c] || c : c);
export const HUBS = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai", "Kolkata", "Ahmedabad"];
const safe = (p, d) => p.catch(() => d);

export async function homeData() {
  const [[c], cityRows, coRows, events, lead, secondary, weekRow] = await Promise.all([
    safe(q(`SELECT (SELECT count(*) FROM companies)::int companies,
      (SELECT count(*) FROM articles WHERE published_at > now()-interval '180 days')::int stories,
      (SELECT count(*) FROM job_postings)::int jobs,
      (SELECT count(*) FROM expansions WHERE event IN ('opened','expanded') AND announced_at > now()-interval '30 days')::int opened30,
      (SELECT count(*) FROM articles WHERE category='leadership' AND published_at > now()-interval '7 days')::int moves7,
      (SELECT count(*) FROM articles WHERE category='funding' AND published_at > now()-interval '30 days')::int deals30,
      (SELECT count(*) FROM articles WHERE published_at > now()-interval '7 days')::int stories7,
      (SELECT count(*) FROM expansions WHERE announced_at > now()-interval '7 days')::int exp7,
      (SELECT max(published_at) FROM articles) latest`), [{}]),
    safe(q("SELECT city,count(*)::int n FROM articles WHERE city IS NOT NULL AND published_at > now()-interval '180 days' GROUP BY 1"), []),
    safe(q("SELECT unnest(india_cities) city,count(*)::int n FROM companies GROUP BY 1"), []),
    safe(q("SELECT city,summary,event,announced_at FROM expansions WHERE city IS NOT NULL AND event<>'closed' ORDER BY announced_at DESC LIMIT 30"), []),
    safe(q(`SELECT * FROM articles WHERE published_at > now()-interval '10 days' ORDER BY (score + comment_count*2) DESC,
      (CASE WHEN category IN ('expansion','funding','policy') THEN 2 WHEN city IS NOT NULL THEN 1 ELSE 0 END) DESC, published_at DESC LIMIT 1`), []),
    safe(q("SELECT * FROM articles ORDER BY published_at DESC NULLS LAST LIMIT 9"), []),
    safe(q(`SELECT to_char(date_trunc('month', published_at),'Mon') m, count(*)::int n FROM articles WHERE published_at > date_trunc('month', now()) - interval '5 months' GROUP BY date_trunc('month', published_at) ORDER BY date_trunc('month', published_at)`), [])]);
  const stats = {};
  for (const r of cityRows) { const h = hub(r.city); (stats[h] ||= { n: 0, c: 0 }).n += r.n; }
  for (const r of coRows) { const h = hub(r.city); (stats[h] ||= { n: 0, c: 0 }).c += r.n; }
  return { c: c || {}, stats, events: events.map(e => ({ city: hub(e.city), text: e.summary, at: e.announced_at, event: e.event })), lead: lead[0], secondary, months: weekRow };
}
export const cat = (name, n = 6) => q("SELECT * FROM articles WHERE category=$1 ORDER BY published_at DESC NULLS LAST LIMIT " + Number(n), [name]).catch(() => []);
export function issueMeta(now = new Date()) {
  const start = new Date(Date.UTC(2026, 4, 4)), days = Math.max(1, Math.floor((now - start) / 864e5) + 1);
  return { issue: days, date: now.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }).toUpperCase() };
}
