import { q } from "../../lib/db";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC events and summits in India" };
const fmt = (d) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
export default async function Events() {
  const rows = await q("SELECT * FROM events ORDER BY starts_on").catch(() => []);
  const today = new Date().toISOString().slice(0, 10), up = rows.filter(e => e.starts_on && e.starts_on.toISOString().slice(0, 10) >= today), past = rows.filter(e => !up.includes(e)).reverse();
  const List = ({ items }) => <ul className="timeline">{items.map(e => <li key={e.id}><span className="ev expanded">{e.starts_on ? fmt(e.starts_on) : "TBA"}</span><div><a href={e.url || e.source_url} target="_blank" rel="nofollow noopener"><b>{e.name}</b></a><div className="mut">{[e.city, e.description].filter(Boolean).join(" · ")}</div></div></li>)}</ul>;
  return (<main className="wrap page"><span className="eyebrow"><i />Calendar</span><h1>Where the GCC world <em>meets.</em></h1>
    <h2>Upcoming</h2><List items={up} />{up.length === 0 && <p className="mut">Nothing verified upcoming.</p>}<h2>Earlier this year</h2><List items={past} /></main>);
}
