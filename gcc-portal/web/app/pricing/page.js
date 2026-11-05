import { PLANS } from "../../lib/plans";
import { getUser } from "../../lib/auth";
import { q } from "../../lib/db";
import TestPlanSwitch from "../../components/TestPlanSwitch";
export const dynamic = "force-dynamic";
export const metadata = { title: "Pricing", description: "Free to read. Pro for the full database, exports and alerts." };
const ROWS = [["Read news, trackers, reports", "✓", "✓", "✓"], ["Weekly digest by email", "✓", "✓", "✓"], ["Comment, upvote, follow", "✓", "✓", "✓"],
  ["Companies visible in search", "25", "All", "All"], ["Jobs per company", "3 latest", "100", "500"], ["Quarter reports: full rankings", "Top 3", "Top 10", "Top 10"],
  ["CSV export", "—", "✓", "✓"], ["Saved companies", "10", "500", "5,000"], ["Saved-search alerts", "—", "10", "100"]];
export default async function Pricing() {
  const u = await getUser(), test = process.env.BILLING_MODE === "test";
  const [c] = await q("SELECT (SELECT count(*) FROM companies)::int co,(SELECT count(*) FROM job_postings)::int jobs,(SELECT count(*) FROM articles)::int arts").catch(() => [{}]);
  return (<main className="wrap page"><span className="eyebrow"><i />Pricing</span><h1>Read for free. <em>Pay when it saves you a week.</em></h1>
    <p className="deck">The news and trackers stay open to everyone. Pro is for people who work the list: sales teams, recruiters, analysts.</p>
    <div className="grid plans" style={{ marginTop: 26 }}>{Object.entries(PLANS).map(([k, p]) => (
      <div key={k} className={"card" + (k === "pro" ? " hl" : "")}><small className="mut">{k === "pro" ? "MOST PEOPLE" : k === "team" ? "FOR TEAMS" : "START HERE"}</small><h3 style={{ margin: "4px 0" }}>{p.label}</h3><h2 style={{ margin: "0 0 6px" }}>{p.price}</h2>
        {k === "free" ? <a className="btn ghost" href={u ? "/dashboard" : "/signup"}>Start free</a>
          : <a className="btn" href={test ? (u ? "/dashboard" : "/signup") : `/dashboard?upgrade=${k}`}>{test ? `Try ${p.label} (test)` : `Choose ${p.label}`}</a>}</div>))}</div>
    <h2>What changes when you upgrade</h2>
    <div className="tablewrap"><table><thead><tr><th /><th>Free</th><th>Pro</th><th>Team</th></tr></thead><tbody>{ROWS.map(r => <tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td><td><b>{r[2]}</b></td><td>{r[3]}</td></tr>)}</tbody></table></div>
    <h2>What is in the database today</h2>
    <div className="stats"><div className="block c1"><b>{c.co}</b><span>companies</span></div><div className="block c2"><b>{c.jobs}</b><span>live India roles</span></div><div className="block c3"><b>{c.arts}</b><span>stories tracked</span></div></div>
    <p className="mut">Every record shows its source and date. How we collect it: <a href="/methodology">methodology</a>.</p>
    {test && u && <TestPlanSwitch current={u.plan} />}
    <p className="mut">{test ? "Test build: payments are off, so plan switching is instant." : "Payments by Razorpay (India) and Stripe (international)."}</p></main>);
}
