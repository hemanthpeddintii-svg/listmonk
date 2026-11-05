import { q } from "../../../lib/db";
import { notFound } from "next/navigation";
import NewsCard from "../../../components/NewsCard";
import { clean, CITY_LIST } from "../../../lib/content";
export const dynamic = "force-dynamic";
export async function generateMetadata({ params }) { const c = decodeURIComponent(params.city); return { title: `GCCs in ${c} – companies, news, jobs`, description: `Global Capability Centers in ${c}: companies, latest news, expansions and hiring.` }; }
export default async function City({ params }) {
  const c = decodeURIComponent(params.city);
  if (!CITY_LIST.includes(c)) notFound();
  const [cos, news, exps, jobs] = await Promise.all([
    q("SELECT id,name,industry FROM companies WHERE $1=ANY(india_cities) ORDER BY last_refreshed_at DESC NULLS LAST LIMIT 30", [c]),
    q("SELECT * FROM articles WHERE city=$1 ORDER BY published_at DESC LIMIT 12", [c]),
    q("SELECT * FROM expansions WHERE city=$1 ORDER BY announced_at DESC LIMIT 8", [c]),
    q("SELECT j.*,c.name company FROM job_postings j JOIN companies c ON c.id=j.company_id WHERE j.location ILIKE $1 ORDER BY first_seen DESC LIMIT 8", [`%${c}%`])]);
  return (<main className="wrap page"><p><a href="/cities">← Cities</a></p><span className="eyebrow"><i />City hub</span><h1>GCCs in <em>{c}</em></h1>
    <h2>Latest news</h2><div className="ngrid">{news.map(a => <NewsCard key={a.id} a={a} />)}</div>{news.length === 0 && <p className="mut">No stories yet.</p>}
    <h2>Expansions</h2><ul>{exps.map(x => <li key={x.id}><span className={"ev " + x.event}>{x.event}</span> <a href={x.source_url} target="_blank" rel="nofollow noopener">{clean(x.summary)}</a></li>)}</ul>
    <h2>Companies ({cos.length})</h2><p>{cos.map(x => <a key={x.id} className="chip" href={`/companies/${x.id}`}>{x.name}</a>)}</p>
    <h2>Jobs</h2><ul>{jobs.map(j => <li key={j.id}><a href={j.url} target="_blank" rel="nofollow noopener">{j.title}</a> — {j.company}</li>)}</ul></main>);
}
