import { q } from "../lib/db";
import { ActionForm } from "../components/Forms";
import { captureLead } from "./actions";
export const dynamic = "force-dynamic";
export default async function Home() {
  const [s] = await q(`SELECT (SELECT count(*) FROM companies)::int companies,
    (SELECT count(*) FROM job_postings)::int jobs, (SELECT count(*) FROM signals)::int signals,
    (SELECT max(last_refreshed_at) FROM companies) refreshed`).catch(() => [{}]);
  return (<main>
    <section className="hero"><h1>The database of every Global Capability Center in India</h1>
      <p>2,000+ GCCs with parent company, cities, headcount, tech stack and live hiring signals — refreshed every 3 days.</p>
      <a className="btn" href="/signup">Get free access</a> <a className="btn ghost" href="/companies">Browse companies</a></section>
    <section className="grid">
      <div className="card stat"><b>{s.companies ?? 0}</b><span className="mut">companies tracked</span></div>
      <div className="card stat"><b>{s.jobs ?? 0}</b><span className="mut">India job postings</span></div>
      <div className="card stat"><b>{s.signals ?? 0}</b><span className="mut">news &amp; expansion signals</span></div>
      <div className="card stat"><b>{s.refreshed ? new Date(s.refreshed).toISOString().slice(0, 10) : "—"}</b><span className="mut">last refresh</span></div>
    </section>
    <h2>Built for sales, recruiting and market research teams</h2>
    <section className="grid">
      <div className="card"><h3>Find the right GCCs</h3><p className="mut">Filter by city, industry, parent company and size.</p></div>
      <div className="card"><h3>Hiring signals</h3><p className="mut">Newest India job postings per company, updated every 3 days.</p></div>
      <div className="card"><h3>Alerts &amp; exports</h3><p className="mut">Save searches, get alerts, export CSV (Pro).</p></div>
    </section>
    <h2>Get the GCC market brief</h2>
    <ActionForm action={captureLead} submit="Email me the brief" className="row"><input name="email" type="email" placeholder="work email" required /></ActionForm>
  </main>);
}
