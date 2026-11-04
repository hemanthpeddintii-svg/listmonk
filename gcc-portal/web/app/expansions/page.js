import { q } from "../../lib/db";
import { quarterOf, ago, clean, CITY_LIST } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC expansion tracker: new and expanding Global Capability Centers in India", description: "Timeline of GCC launches, expansions and closures in India, grouped by quarter, with city filter and verification status." };
const ICON = { opened: "Opened", expanded: "Expanded", closed: "Closed", announced: "Announced" }, PAGE = 40;
export default async function Expansions({ searchParams: sp }) {
  const page = Math.max(1, Number(sp.page) || 1), where = [], args = [];
  if (sp.event) { args.push(sp.event); where.push(`event=$${args.length}`); }
  if (sp.city) { args.push(sp.city); where.push(`city=$${args.length}`); }
  if (sp.v) where.push("verified");
  const w = where.length ? "WHERE " + where.join(" AND ") : "";
  const [{ n }] = await q(`SELECT count(*)::int n FROM expansions ${w}`, args);
  const rows = await q(`SELECT * FROM expansions ${w} ORDER BY announced_at DESC LIMIT ${PAGE} OFFSET ${(page - 1) * PAGE}`, args);
  const groups = {}; for (const r of rows) { const k = `${new Date(r.announced_at).getUTCFullYear()} · ${quarterOf(r.announced_at)}`; (groups[k] ||= []).push(r); }
  const qs = (o) => "?" + new URLSearchParams(Object.entries({ ...sp, ...o }).filter(([, v]) => v)).toString();
  return (<main className="wrap page"><span className="eyebrow"><i />Tracker</span><h1>Who is opening, expanding <em>or closing</em> a GCC?</h1>
    <p className="deck">Detected from headlines, then checked by our team. Verified entries carry a badge; the rest are marked as detected.</p>
    <div className="tabs">{["", "opened", "expanded", "closed"].map(e => <a key={e} className={(sp.event || "") === e ? "on" : ""} href={qs({ event: e, page: "" })}>{e || "all"}</a>)}<a className={sp.v ? "on" : ""} href={qs({ v: sp.v ? "" : "1", page: "" })}>verified only</a></div>
    <form className="row"><select name="city" defaultValue={sp.city || ""} aria-label="City"><option value="">All cities</option>{CITY_LIST.map(c => <option key={c}>{c}</option>)}</select><button className="btn ghost">Filter</button><span className="mut">{n} entries</span></form>
    {Object.entries(groups).map(([k, items]) => (<section key={k}><h2 className="qhead">{k}<small>{items.length}</small></h2>
      <ul className="timeline">{items.map(r => (<li key={r.id}><span className={"ev " + r.event}>{ICON[r.event]}</span>
        <div><a href={r.source_url} target="_blank" rel="nofollow noopener"><b>{clean(r.summary || r.company_name)}</b></a>
          <div className="mut">{[r.city, ago(r.announced_at)].filter(Boolean).join(" · ")} · <span className={"verified " + (r.verified ? "y" : "n")}>{r.verified ? "Verified" : "Detected"}</span></div></div></li>))}</ul></section>))}
    {rows.length === 0 && <p className="mut">Nothing matches.</p>}
    <div className="pager">{page > 1 && <a href={qs({ page: page - 1 })}>← Newer</a>}{page * PAGE < n && <a href={qs({ page: page + 1 })}>Older →</a>}</div></main>);
}
