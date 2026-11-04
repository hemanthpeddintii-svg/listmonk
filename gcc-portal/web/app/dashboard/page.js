import { q } from "../../lib/db";
import { requireUser, planOf } from "../../lib/auth";
import { PLANS } from "../../lib/plans";
export const dynamic = "force-dynamic";
export const metadata = { title: "Dashboard" };
export default async function Dashboard({ searchParams }) {
  const u = await requireUser(); const p = planOf(u);
  const saved = await q(`SELECT c.id,c.name,c.industry,c.last_refreshed_at,
      (SELECT count(*)::int FROM job_postings j WHERE j.company_id=c.id) jobs
    FROM saved_companies s JOIN companies c ON c.id=s.company_id WHERE s.user_id=$1 ORDER BY s.created_at DESC`, [u.id]);
  const alerts = await q("SELECT id,name,query FROM saved_searches WHERE user_id=$1 ORDER BY id DESC", [u.id]);
  const up = PLANS[searchParams.upgrade] && searchParams.upgrade !== "free" ? searchParams.upgrade : null;
  return (<main><h1>Welcome{u.name ? `, ${u.name}` : ""}</h1>
    <div className="card">Plan: <b>{p.label}</b>{u.plan_expires_at && <> · renews/expires {new Date(u.plan_expires_at).toISOString().slice(0, 10)}</>}
      {up && <p>To upgrade to <b>{PLANS[up].label}</b> ({PLANS[up].price}) online checkout is being connected — contact us and an admin can enable it.</p>}
      {u.plan === "free" && !up && <p><a href="/pricing">Upgrade</a> for the full database, exports and alerts.</p>}</div>
    <h2>Saved companies ({saved.length}/{p.saved})</h2>
    <ul>{saved.map(c => <li key={c.id}><a href={`/companies/${c.id}`}>{c.name}</a> <span className="mut">{c.industry} · {c.jobs} jobs</span></li>)}</ul>
    {saved.length === 0 && <p className="mut">Star companies in the <a href="/companies">explorer</a> to track them here.</p>}
    <h2>Alerts</h2>
    <ul>{alerts.map(a => <li key={a.id}>{a.name} <span className="mut">{JSON.stringify(a.query)}</span></li>)}</ul>
    {alerts.length === 0 && <p className="mut">{p.alerts ? "Create alerts from the explorer." : "Alerts are a Pro feature."}</p>}</main>);
}
