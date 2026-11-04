import { pool, currentPlan } from "../../lib/db";
export const dynamic = "force-dynamic";
export default async function Companies() {
  const plan = currentPlan();
  const limit = plan === "free" ? 25 : 500;
  const { rows } = await pool.query(
    `SELECT c.name,c.parent_company,c.india_cities,c.industry,c.last_refreshed_at,
       (SELECT count(*) FROM job_postings j WHERE j.company_id=c.id) AS open_jobs
     FROM companies c ORDER BY c.name LIMIT $1`, [limit]);
  return (<main><h1>Companies</h1>
    {plan === "free" && <p>Free plan: showing 25. <a href="/pricing">Upgrade</a> for all.</p>}
    <table><thead><tr><th>Name</th><th>Parent</th><th>Cities</th><th>Industry</th>
      <th>{plan==="free" ? "Open jobs 🔒" : "Open jobs"}</th><th>Updated</th></tr></thead>
    <tbody>{rows.map(r => (<tr key={r.name}><td>{r.name}</td><td>{r.parent_company}</td>
      <td>{(r.india_cities||[]).join(", ")}</td><td>{r.industry}</td>
      <td>{plan==="free" ? "—" : r.open_jobs}</td>
      <td>{r.last_refreshed_at?.toISOString().slice(0,10) ?? "pending"}</td></tr>))}</tbody></table></main>);
}
