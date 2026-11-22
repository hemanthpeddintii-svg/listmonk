import { q } from "../../lib/db";
import { clean, ago } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "People moves: who is heading India's GCCs", description: "Appointments and leadership changes at Global Capability Centers in India, newest first." };
export default async function People() {
  const moves = await q("SELECT * FROM people_moves ORDER BY published_at DESC NULLS LAST LIMIT 120").catch(() => []);
  const stories = await q("SELECT id,title,source_name,published_at,city FROM articles WHERE category='leadership' ORDER BY published_at DESC LIMIT 80").catch(() => []);
  return (<main className="wrap page"><span className="eyebrow"><i />Tracker</span><h1>Who moved, <em>and where.</em></h1>
    <p className="deck">Leadership appointments at GCCs in India. The people who sign off on vendors, hiring plans and new sites.</p>
    {moves.length > 0 && <><h2>Structured moves</h2><div className="tablewrap"><table><thead><tr><th>Person</th><th>Role</th><th>Company</th><th>City</th><th>When</th><th /></tr></thead>
      <tbody>{moves.map(m => <tr key={m.id}><td><b>{m.person}</b></td><td>{m.role}</td><td>{m.company_id ? <a href={`/companies/${m.company_id}`}>{m.company_name}</a> : m.company_name}</td><td>{m.city}</td><td>{m.published_at ? ago(m.published_at) : ""}</td><td><a href={m.source_url} target="_blank" rel="nofollow noopener">source ↗</a></td></tr>)}</tbody></table></div></>}
    <h2>Leadership headlines</h2>
    <ul className="timeline">{stories.map(a => <li key={a.id}><span className="ev expanded">{ago(a.published_at)}</span><div><a href={`/story/${a.id}`}><b>{clean(a.title)}</b></a><div className="mut">{a.source_name}{a.city && ` · ${a.city}`}</div></div></li>)}</ul>
    {stories.length === 0 && moves.length === 0 && <p className="mut">No moves tracked yet.</p>}</main>);
}
