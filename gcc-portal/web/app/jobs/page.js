import { q } from "../../lib/db";
import { getUser, planOf } from "../../lib/auth";
import { ago } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC jobs in India – latest openings at Global Capability Centers" };
export default async function Jobs() {
  const u = await getUser(), p = planOf(u);
  const rows = await q(`SELECT j.*,c.name company,c.id cid FROM job_postings j JOIN companies c ON c.id=j.company_id ORDER BY j.first_seen DESC LIMIT ${u ? (p.export ? 200 : 25) : 10}`);
  return (<main className="wrap page"><span className="eyebrow"><i />Hiring signals</span><h1>Latest GCC jobs, <em>newest first.</em></h1>
    <ul className="timeline">{rows.map(j => <li key={j.id}><span className="ev opened">{ago(j.first_seen)}</span><div><a href={j.url} target="_blank" rel="nofollow noopener"><b>{j.title}</b></a><div className="mut"><a href={`/companies/${j.cid}`}>{j.company}</a> · {j.location}</div></div></li>)}</ul>
    {rows.length === 0 && <p className="mut">No postings yet — the weekly refresh fills this.</p>}
    {!u && <p className="lock"><a href="/signup">Sign up free</a> to see more.</p>}</main>);
}
