import { q } from "../../lib/db";
import NewsCard from "../../components/NewsCard";
import { CITY_LIST } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC news India – latest on Global Capability Centers", description: "Every headline on GCCs in India: new centres, expansions, hiring and leadership moves — newest first." };
const PAGE = 24;
export default async function News({ searchParams: sp }) {
  const page = Math.max(1, Number(sp.page) || 1), where = [], args = [];
  if (sp.city) { args.push(sp.city); where.push(`city=$${args.length}`); }
  if (sp.kind) { args.push(sp.kind); where.push(`kind=$${args.length}`); }
  if (sp.cat) { args.push(sp.cat); where.push(`category=$${args.length}`); }
  if (sp.q) { args.push(`%${sp.q}%`); where.push(`title ILIKE $${args.length}`); }
  const w = where.length ? "WHERE " + where.join(" AND ") : "";
  const [{ n }] = await q(`SELECT count(*)::int n FROM articles ${w}`, args);
  const rows = await q(`SELECT * FROM articles ${w} ORDER BY ${sp.sort === "top" ? "(score + comment_count*2) DESC, " : ""}published_at DESC NULLS LAST LIMIT ${PAGE} OFFSET ${(page - 1) * PAGE}`, args);
  const qs = (o) => "?" + new URLSearchParams(Object.entries({ ...sp, ...o }).filter(([, v]) => v)).toString();
  return (<main className="wrap page"><span className="eyebrow"><i />Updated every 3 days</span><h1>GCC news, <em>newest first.</em></h1>
    <div className="tabs">{["", "expansion", "leadership", "funding", "hiring", "policy", "ai"].map(c => <a key={c} className={(sp.cat || "") === c ? "on" : ""} href={qs({ cat: c, page: "" })}>{c || "all"}</a>)}
      <span style={{ flex: 1 }} /><a className={sp.sort === "top" ? "on" : ""} href={qs({ sort: sp.sort === "top" ? "" : "top", page: "" })}>★ top</a></div>
    <form className="row"><input name="q" placeholder="Search headlines" defaultValue={sp.q} />
      <select name="city" defaultValue={sp.city || ""}><option value="">All cities</option>{CITY_LIST.map(c => <option key={c}>{c}</option>)}</select>
      <select name="kind" defaultValue={sp.kind || ""}><option value="">All types</option><option value="news">News</option><option value="analysis">Analysis</option><option value="explainer">Explainers</option></select>
      <button className="btn">Filter</button></form>
    <p className="mut">{n} stories</p>
    <div className="ngrid">{rows.map((a, i) => <NewsCard key={a.id} a={a} big={i === 0 && page === 1 && !sp.q} />)}</div>
    {rows.length === 0 && <p className="mut">No stories match.</p>}
    <div className="pager">{page > 1 && <a href={qs({ page: page - 1 })}>← Newer</a>}{page * PAGE < n && <a href={qs({ page: page + 1 })}>Older →</a>}</div></main>);
}
