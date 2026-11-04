import { q } from "../../lib/db";
import { requireAdmin } from "../../lib/auth";
import { ActionForm } from "../../components/Forms";
import { importCompanies, setPlan } from "../actions";
export const dynamic = "force-dynamic";
export const metadata = { title: "Admin" };
export default async function Admin() {
  await requireAdmin();
  const [s] = await q(`SELECT (SELECT count(*) FROM companies)::int companies,(SELECT count(*) FROM users)::int users,
    (SELECT count(*) FROM users WHERE plan<>'free')::int paid,(SELECT count(*) FROM leads)::int leads,
    (SELECT count(*) FROM companies WHERE last_refreshed_at IS NULL OR last_refreshed_at < now()-interval '3 days')::int stale`);
  const users = await q("SELECT id,email,plan,role,created_at FROM users ORDER BY id DESC LIMIT 50");
  const runs = await q("SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 10");
  return (<main className="wrap page"><h1>Admin</h1>
    <div className="grid">{Object.entries(s).map(([k, v]) => <div key={k} className="card stat"><b>{v}</b><span className="mut">{k}</span></div>)}</div>
    <h2>Import companies (CSV)</h2>
    <p className="mut">Columns: name, domain, parent_company, hq_country, cities (;-separated), industry, gcc_function, india_headcount_range, year_established, tech_stack, careers_url</p>
    <ActionForm action={importCompanies} submit="Import"><input type="file" name="file" accept=".csv" required /></ActionForm>
    <h2>Recent ingestion runs</h2>
    <ul>{runs.map(r => <li key={r.id}>{r.kind} · {r.rows_ok}/{r.rows_in} · {r.started_at.toISOString().slice(0, 16)}</li>)}</ul>
    <h2>Users</h2><div className="tablewrap"><table><thead><tr><th>Email</th><th>Plan</th><th>Role</th><th>Set plan</th></tr></thead>
      <tbody>{users.map(u => <tr key={u.id}><td>{u.email}</td><td>{u.plan}</td><td>{u.role}</td><td>
        <form action={setPlan} className="row" style={{ margin: 0 }}><input type="hidden" name="id" value={u.id} />
          <select name="plan" defaultValue={u.plan}><option>free</option><option>pro</option><option>team</option></select><button className="btn ghost">Set</button></form></td></tr>)}</tbody></table></div>
    <p className="mut">Data refresh runs via <code>workers/refresh.py</code> every 3 days (cron/GitHub Actions).</p></main>);
}
