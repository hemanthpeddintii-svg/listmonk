import { q } from "../../lib/db";
import { clean, ago } from "../../lib/content";
export const dynamic = "force-dynamic";
export const metadata = { title: "Search" };
export default async function Search({ searchParams: sp }) {
  const term = (sp.q || "").trim().slice(0, 80), like = `%${term}%`;
  const [arts, cos, people] = term ? await Promise.all([
    q("SELECT id,title,source_name,published_at,city FROM articles WHERE title ILIKE $1 ORDER BY published_at DESC NULLS LAST LIMIT 30", [like]),
    q("SELECT id,name,parent_company,industry FROM companies WHERE name ILIKE $1 OR parent_company ILIKE $1 ORDER BY name LIMIT 20", [like]),
    q("SELECT person,role,company_name,source_url FROM people_moves WHERE person ILIKE $1 OR company_name ILIKE $1 LIMIT 10", [like]).catch(() => [])]) : [[], [], []];
  return (<main className="wrap page"><h1>Search <em>everything.</em></h1>
    <form className="row"><input aria-label="Company, city, person, topic" name="q" defaultValue={term} placeholder="Company, city, person, topic" autoFocus style={{ minWidth: 320 }} /><button className="btn">Search</button></form>
    {term && <><h2>Companies ({cos.length})</h2><p>{cos.map(c => <a key={c.id} className="chip" href={`/companies/${c.id}`}>{c.name}</a>)}</p>
      {people.length > 0 && <><h2>People</h2><ul>{people.map((p, i) => <li key={i}><a href={p.source_url} target="_blank" rel="nofollow noopener">{p.person}</a>, {p.role} at {p.company_name}</li>)}</ul></>}
      <h2>Stories ({arts.length})</h2><ul className="timeline">{arts.map(a => <li key={a.id}><span className="ev">{ago(a.published_at)}</span><div><a href={`/story/${a.id}`}><b>{clean(a.title)}</b></a><div className="mut">{a.source_name}{a.city && ` · ${a.city}`}</div></div></li>)}</ul>
      {arts.length + cos.length === 0 && <p className="mut">Nothing found for &ldquo;{term}&rdquo;.</p>}</>}</main>);
}
