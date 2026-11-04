import { q } from "../../lib/db";
import { getUser, planOf } from "../../lib/auth";
import { toggleSave, saveSearch } from "../actions";
import { ActionForm } from "../../components/Forms";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC companies in India" };
const PAGE = 25;

async function search({ q: term = "", city = "", industry = "", page = 1 }, limit) {
  const where = [], args = [];
  if (term) { args.push(`%${term}%`); where.push(`(c.name ILIKE $${args.length} OR c.parent_company ILIKE $${args.length})`); }
  if (city) { args.push(city); where.push(`$${args.length} = ANY(c.india_cities)`); }
  if (industry) { args.push(industry); where.push(`c.industry = $${args.length}`); }
  const w = where.length ? "WHERE " + where.join(" AND ") : "";
  const [{ n }] = await q(`SELECT count(*)::int n FROM companies c ${w}`, args);
  const shown = Math.min(n, limit);
  const offset = (Math.max(1, page) - 1) * PAGE;
  args.push(Math.max(0, Math.min(PAGE, shown - offset)), offset);
  const rows = await q(
    `SELECT c.id,c.name,c.parent_company,c.india_cities,c.industry,c.last_refreshed_at,
       (SELECT count(*)::int FROM job_postings j WHERE j.company_id=c.id) open_jobs
     FROM companies c ${w}
     ORDER BY c.last_refreshed_at DESC NULLS LAST, c.name
     LIMIT $${args.length - 1} OFFSET $${args.length}`, args);
  return { rows, total: n, shown };
}

export default async function Companies({ searchParams: sp }) {
  const u = await getUser(); const plan = planOf(u);
  const page = Number(sp.page) || 1;
  const { rows, total, shown } = await search({ q: sp.q, city: sp.city, industry: sp.industry, page }, plan.maxRows);
  const [cities, inds] = await Promise.all([
    q("SELECT DISTINCT unnest(india_cities) c FROM companies ORDER BY 1"),
    q("SELECT DISTINCT industry i FROM companies WHERE industry IS NOT NULL ORDER BY 1")]);
  const saved = u ? new Set((await q("SELECT company_id FROM saved_companies WHERE user_id=$1", [u.id])).map(r => r.company_id)) : new Set();
  const qs = (o) => "?" + new URLSearchParams(Object.entries({ ...sp, ...o }).filter(([, v]) => v)).toString();
  return (<main className="wrap page"><h1>GCC companies in India</h1>
    <form className="row"><input name="q" placeholder="Search company or parent" defaultValue={sp.q} />
      <select name="city" defaultValue={sp.city || ""}><option value="">All cities</option>{cities.map(r => <option key={r.c}>{r.c}</option>)}</select>
      <select name="industry" defaultValue={sp.industry || ""}><option value="">All industries</option>{inds.map(r => <option key={r.i}>{r.i}</option>)}</select>
      <button className="btn">Search</button>
      {plan.export && <a className="btn ghost" href={"/api/export" + qs({ page: "" })}>Export CSV</a>}</form>
    <p className="mut">{total} companies · newest-refreshed first{total > shown && <> · showing first {shown} on your plan. <a href="/pricing">Upgrade</a></>}</p>
    {u && plan.alerts > 0 && <ActionForm action={saveSearch} submit="🔔 Alert me" className="row">
      <input type="hidden" name="q" value={sp.q || ""} /><input type="hidden" name="city" value={sp.city || ""} /><input type="hidden" name="industry" value={sp.industry || ""} />
      <input name="name" placeholder="Name this alert" /></ActionForm>}
    <div className="tablewrap"><table><thead><tr><th>Company</th><th>Parent</th><th>Cities</th><th>Industry</th><th>Open jobs</th><th>Updated</th><th /></tr></thead>
      <tbody>{rows.map(r => (<tr key={r.id}>
        <td><a href={`/companies/${r.id}`}>{r.name}</a></td><td>{r.parent_company}</td>
        <td>{(r.india_cities || []).join(", ")}</td><td>{r.industry && <span className="tag">{r.industry}</span>}</td>
        <td>{u ? r.open_jobs : <a className="lock" href="/signup">🔒</a>}</td>
        <td>{r.last_refreshed_at?.toISOString().slice(0, 10) ?? "pending"}</td>
        <td>{u && <form action={toggleSave.bind(null, r.id)}><button className="btn ghost">{saved.has(r.id) ? "★" : "☆"}</button></form>}</td></tr>))}</tbody></table></div>
    {rows.length === 0 && <p className="mut">No companies yet — an admin can import data at /admin.</p>}
    <div className="pager">{page > 1 && <a href={qs({ page: page - 1 })}>← Newer</a>}
      {page * PAGE < shown && <a href={qs({ page: page + 1 })}>Older →</a>}</div></main>);
}
