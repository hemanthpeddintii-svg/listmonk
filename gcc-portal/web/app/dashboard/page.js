import { q } from "../../lib/db";
import { requireUser, planOf } from "../../lib/auth";
import TestPlanSwitch from "../../components/TestPlanSwitch";
import { PLANS } from "../../lib/plans";
import { getFollows, getFeed, getFeedCount } from "../../lib/community";
import { ago, clean } from "../../lib/content";
import "../community.css";
export const dynamic = "force-dynamic";
export const metadata = { title: "Dashboard" };
export default async function Dashboard({ searchParams }) {
  const u = await requireUser(); const p = planOf(u);
  const saved = await q(`SELECT c.id,c.name,c.industry,c.last_refreshed_at,
      (SELECT count(*)::int FROM job_postings j WHERE j.company_id=c.id) jobs
    FROM saved_companies s JOIN companies c ON c.id=s.company_id WHERE s.user_id=$1 ORDER BY s.created_at DESC`, [u.id]);
  const alerts = await q("SELECT id,name,query FROM saved_searches WHERE user_id=$1 ORDER BY id DESC", [u.id]);
  const [fol, feed, week] = await Promise.all([getFollows(u.id), getFeed(u.id, 8), getFeedCount(u.id, 7)]);
  const up = PLANS[searchParams.upgrade] && searchParams.upgrade !== "free" ? searchParams.upgrade : null;
  return (<main className="wrap page"><h1>Welcome{u.name ? `, ${u.name}` : ""}</h1>
    <div className="card">Plan: <b>{p.label}</b>{u.plan_expires_at && <> · renews/expires {new Date(u.plan_expires_at).toISOString().slice(0, 10)}</>}
      {up && <p>To upgrade to <b>{PLANS[up].label}</b> ({PLANS[up].price}) online checkout is being connected — contact us and an admin can enable it.</p>}
      {u.plan === "free" && !up && <p><a href="/pricing">Upgrade</a> for the full database, exports and alerts.</p>}</div>
    <TestPlanSwitch current={u.plan} />
    <h2>Your feed</h2>
    <div className="fcounts"><div className="fcount"><b>{fol.company.length}</b><span>Companies followed</span></div><div className="fcount"><b>{fol.city.length}</b><span>Cities</span></div>
      <div className="fcount"><b>{fol.topic.length}</b><span>Topics</span></div><div className="fcount" style={{ background: "var(--lime)" }}><b>{week}</b><span>New this week</span></div></div>
    {feed.length > 0 ? <ul className="feed" style={{ marginTop: 14 }}>{feed.map(a => <li key={a.id}><a className="h" href={`/story/${a.id}`}>{clean(a.title)}</a>
        <span className="s">{a.comment_count} comment{a.comment_count === 1 ? "" : "s"}</span>
        <span className="m"><span>{a.source_name || "GCC Intel"}</span><span>{ago(a.published_at)}</span>{a.city && <span>{a.city}</span>}{a.company_name && <span>{a.company_name}</span>}</span></li>)}</ul>
      : <p className="mut">{fol.total ? "No stories match your follows yet." : "Follow cities, topics or companies and their newest headlines show up here."}</p>}
    <p><a href="/following">Following ({fol.total}) →</a></p>
    <h2>Saved companies ({saved.length}/{p.saved})</h2>
    <ul>{saved.map(c => <li key={c.id}><a href={`/companies/${c.id}`}>{c.name}</a> <span className="mut">{c.industry} · {c.jobs} jobs</span></li>)}</ul>
    {saved.length === 0 && <p className="mut">Star companies in the <a href="/companies">explorer</a> to track them here.</p>}
    <h2>Alerts</h2>
    <ul>{alerts.map(a => <li key={a.id}>{a.name} <span className="mut">{JSON.stringify(a.query)}</span></li>)}</ul>
    {alerts.length === 0 && <p className="mut">{p.alerts ? "Create alerts from the explorer." : "Alerts are a Pro feature."}</p>}</main>);
}
