import { q } from "../../lib/db";
import { CITY_LIST } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC hubs in India – Bengaluru, Hyderabad, Pune, Chennai, NCR, Mumbai" };
export default async function Cities() {
  const rows = await q("SELECT city,count(*)::int n FROM articles WHERE city IS NOT NULL GROUP BY 1");
  const n = Object.fromEntries(rows.map(r => [r.city, r.n]));
  return (<main className="wrap page"><span className="eyebrow"><i />City hubs</span><h1>Every GCC city, <em>one page each.</em></h1>
    <div className="grid">{CITY_LIST.map(c => <a key={c} className="card" href={`/cities/${encodeURIComponent(c)}`}><h2 style={{ margin: 0 }}>{c}</h2><span className="mut">{n[c] || 0} stories</span></a>)}</div></main>);
}
