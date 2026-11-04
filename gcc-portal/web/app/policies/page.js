import { q } from "../../lib/db";
export const dynamic = "force-dynamic";
export const metadata = { title: "State GCC policies in India: incentives compared", description: "Which Indian states have a dedicated GCC policy, what it offers, and the source for each." };
export default async function Policies() {
  const rows = await q("SELECT * FROM policies ORDER BY year DESC NULLS LAST, state").catch(() => []);
  return (<main className="wrap page"><span className="eyebrow"><i />Tracker</span><h1>Every state wants <em>your GCC.</em></h1>
    <p className="deck">What each state actually offers, with the source we read. Where we could not confirm a dedicated policy, we say so.</p>
    <div className="pol">{rows.map(p => (<div key={p.id} className="card"><small className="mut">{p.state}{p.year && ` · ${p.year}`}</small><h3>{p.name}</h3><p>{p.summary}</p>
      {p.incentives?.length > 0 && <ul>{p.incentives.map(i => <li key={i}>{i}</li>)}</ul>}{p.source_url && <a href={p.source_url} target="_blank" rel="nofollow noopener">Source ↗</a>}</div>))}</div>
    {rows.length === 0 && <p className="mut">Policy tracker is being compiled.</p>}</main>);
}
