import { q } from "../../lib/db";
import { clean, ago } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC ecosystem deals and funding", description: "Funding rounds and deals in the GCC ecosystem: enablement startups, GCC-focused funds and capability-center acquisitions." };
export default async function Deals() {
  const rows = await q("SELECT * FROM fundings ORDER BY published_at DESC NULLS LAST LIMIT 120").catch(() => []);
  const stories = await q("SELECT id,title,source_name,published_at FROM articles WHERE category='funding' ORDER BY published_at DESC LIMIT 80").catch(() => []);
  return (<main className="wrap page"><span className="eyebrow"><i />Tracker</span><h1>Who raised, <em>who bought, who built.</em></h1>
    <p className="deck">Money moving through the GCC ecosystem: enablement startups, services firms, funds and deals that create capability centers.</p>
    {rows.length > 0 && <><h2>Structured deals</h2><div className="tablewrap"><table><thead><tr><th>Company</th><th>Type</th><th>Amount</th><th>Round</th><th>When</th><th /></tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}><td><b>{r.company_name}</b></td><td>{r.kind}</td><td>{r.amount_text}</td><td>{r.round}</td><td>{r.published_at ? ago(r.published_at) : ""}</td><td><a href={r.source_url} target="_blank" rel="nofollow noopener">source ↗</a></td></tr>)}</tbody></table></div></>}
    <h2>Deal headlines</h2>
    <ul className="timeline">{stories.map(a => <li key={a.id}><span className="ev opened">{ago(a.published_at)}</span><div><a href={`/story/${a.id}`}><b>{clean(a.title)}</b></a><div className="mut">{a.source_name}</div></div></li>)}</ul>
    {stories.length === 0 && rows.length === 0 && <p className="mut">No deals tracked yet.</p>}</main>);
}
