import { pool, currentPlan } from "../../../lib/db";
export const dynamic = "force-dynamic";
export default async function Company({ params }) {
  const plan = currentPlan();
  const { rows: [c] } = await pool.query("SELECT * FROM companies WHERE id=$1", [params.id]);
  if (!c) return <main>Not found</main>;
  // Newest first. Free plan sees only the 3 latest items.
  const cap = plan === "free" ? 3 : 100;
  const { rows: jobs } = await pool.query(
    "SELECT * FROM job_postings WHERE company_id=$1 ORDER BY first_seen DESC LIMIT $2", [c.id, cap]);
  const { rows: sigs } = await pool.query(
    "SELECT * FROM signals WHERE company_id=$1 ORDER BY published_at DESC NULLS LAST LIMIT $2", [c.id, cap]);
  return (<main><h1>{c.name}</h1>
    <p>{c.parent_company} · {c.hq_country} · {(c.india_cities||[]).join(", ")} · {c.industry}</p>
    <p>Last refreshed: {c.last_refreshed_at?.toISOString() ?? "pending"}</p>
    <h2>Latest signals</h2><ul>{sigs.map(s=><li key={s.id}><a href={s.url}>{s.headline}</a> <small>{s.published_at?.toISOString().slice(0,10)}</small></li>)}</ul>
    <h2>Latest India jobs</h2><ul>{jobs.map(j=><li key={j.id}><a href={j.url}>{j.title}</a> – {j.location} <small>{j.first_seen.toISOString().slice(0,10)}</small></li>)}</ul>
    {plan==="free" && <p>🔒 <a href="/pricing">Upgrade</a> for full history.</p>}</main>);
}
