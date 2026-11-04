import { q } from "../../lib/db";
import { quarterOf, ago, clean } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC expansion tracker – new & expanding Global Capability Centers in India", description: "Timeline of GCC launches, expansions and closures in India, grouped by year and quarter." };
const ICON = { opened: "● Opened", expanded: "▲ Expanded", closed: "✕ Closed", announced: "◆ Announced" };
export default async function Expansions({ searchParams: sp }) {
  const rows = await q(`SELECT * FROM expansions ${sp.event ? "WHERE event=$1" : ""} ORDER BY announced_at DESC LIMIT 300`, sp.event ? [sp.event] : []);
  const groups = {}; for (const r of rows) { const k = `${new Date(r.announced_at).getUTCFullYear()} · ${quarterOf(r.announced_at)}`; (groups[k] ||= []).push(r); }
  return (<main className="wrap page"><span className="eyebrow"><i />Tracker</span><h1>Who is opening, expanding <em>or closing</em> a GCC?</h1>
    <p className="mut">Auto-detected from headlines (unverified) and edited by our team (verified ✓). Grouped by quarter, newest first.</p>
    <p>{["", "opened", "expanded", "closed"].map(e => <a key={e} className={"chip" + ((sp.event || "") === e ? " on" : "")} href={e ? `?event=${e}` : "?"}>{e || "all"}</a>)}</p>
    {Object.entries(groups).map(([k, items]) => (<section key={k}><h2 className="qhead">{k}<small>{items.length}</small></h2>
      <ul className="timeline">{items.map(r => (<li key={r.id}><span className={"ev " + r.event}>{ICON[r.event]}</span>
        <div><a href={r.source_url} target="_blank" rel="nofollow noopener"><b>{clean(r.summary || r.company_name)}</b></a>
          <div className="mut">{[r.city, r.verified ? "verified ✓" : "auto-detected", ago(r.announced_at)].filter(Boolean).join(" · ")}</div></div></li>))}</ul></section>))}
    {rows.length === 0 && <p className="mut">Nothing yet — run <code>workers/news.py</code> or add entries in admin.</p>}</main>);
}
