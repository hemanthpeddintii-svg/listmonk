import { notFound } from "next/navigation";
import { q } from "../../../lib/db";
import { getUser, planOf } from "../../../lib/auth";
import { toggleSave } from "../../actions";
export const dynamic = "force-dynamic";
export async function generateMetadata({ params }) {
  const [c] = await q("SELECT name FROM companies WHERE id=$1", [Number(params.id) || 0]);
  return { title: c ? `${c.name} GCC in India` : "Not found" };
}
const d = (x) => (x ? new Date(x).toISOString().slice(0, 10) : "");
export default async function Company({ params }) {
  const id = Number(params.id) || 0;
  const u = await getUser(); const p = planOf(u);
  const [c] = await q("SELECT * FROM companies WHERE id=$1", [id]);
  if (!c) notFound();
  const [jobs, sigs, [sv]] = await Promise.all([
    q("SELECT * FROM job_postings WHERE company_id=$1 ORDER BY first_seen DESC LIMIT $2", [id, p.jobs]),
    q("SELECT * FROM signals WHERE company_id=$1 ORDER BY published_at DESC NULLS LAST, id DESC LIMIT $2", [id, p.signals]),
    u ? q("SELECT 1 FROM saved_companies WHERE user_id=$1 AND company_id=$2", [u.id, id]) : [null]]);
  const [{ nj, ns }] = await q("SELECT (SELECT count(*)::int FROM job_postings WHERE company_id=$1) nj,(SELECT count(*)::int FROM signals WHERE company_id=$1) ns", [id]);
  return (<main>
    <p><a href="/companies">← All companies</a></p>
    <h1>{c.name}</h1>
    <p className="mut">{[c.parent_company, c.hq_country, (c.india_cities || []).join(", "), c.industry].filter(Boolean).join(" · ")}</p>
    {u && <form action={toggleSave.bind(null, id)}><button className="btn ghost">{sv ? "★ Saved" : "☆ Save"}</button></form>}
    <section className="grid" style={{ margin: "16px 0" }}>
      <div className="card"><span className="mut">India headcount</span><br />{c.india_headcount_range || "—"}</div>
      <div className="card"><span className="mut">GCC function</span><br />{c.gcc_function || "—"}</div>
      <div className="card"><span className="mut">Established</span><br />{c.year_established || "—"}</div>
      <div className="card"><span className="mut">Last refreshed</span><br />{d(c.last_refreshed_at) || "pending"}</div></section>
    {c.tech_stack?.length > 0 && <p>{c.tech_stack.map(t => <span key={t} className="tag" style={{ marginRight: 6 }}>{t}</span>)}</p>}
    <h2>Latest signals</h2>
    <ul>{sigs.map(s => <li key={s.id}><a href={s.url} rel="nofollow noopener">{s.headline}</a> <small className="mut">{d(s.published_at)}</small></li>)}</ul>
    {sigs.length === 0 && <p className="mut">None yet.</p>}
    <h2>Latest India jobs</h2>
    <ul>{jobs.map(j => <li key={j.id}><a href={j.url} rel="nofollow noopener">{j.title}</a> — {j.location} <small className="mut">{d(j.first_seen)}</small></li>)}</ul>
    {jobs.length === 0 && <p className="mut">None yet.</p>}
    {(nj > jobs.length || ns > sigs.length) && <p className="lock">🔒 Showing latest {p.jobs} items. <a href="/pricing">Upgrade</a> for full history.</p>}
  </main>);
}
