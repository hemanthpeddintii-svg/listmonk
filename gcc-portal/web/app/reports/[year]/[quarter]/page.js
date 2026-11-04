import { notFound } from "next/navigation";
import { q } from "../../../../lib/db";
import { bounds, clean } from "../../../../lib/content";
import { getUser, planOf } from "../../../../lib/auth";
export const dynamic = "force-dynamic";
export async function generateMetadata({ params }) { return { title: `GCC India ${params.year} ${params.quarter.toUpperCase()} report` }; }
export default async function Report({ params }) {
  const y = Number(params.year), qn = Number(params.quarter.replace(/q/i, ""));
  if (!(y >= 2020 && y <= 2100 && qn >= 1 && qn <= 4)) notFound();
  const [s, e] = bounds(y, qn), u = await getUser(), p = planOf(u), A = [s, e], top = p.export ? 10 : 3;
  const [[m], cities, cos, exps, news] = await Promise.all([
    q(`SELECT (SELECT count(*) FROM articles WHERE published_at>=$1 AND published_at<$2)::int news,
        (SELECT count(*) FROM expansions WHERE announced_at>=$1 AND announced_at<$2 AND event='opened')::int opened,
        (SELECT count(*) FROM expansions WHERE announced_at>=$1 AND announced_at<$2 AND event='expanded')::int expanded,
        (SELECT count(*) FROM expansions WHERE announced_at>=$1 AND announced_at<$2 AND event='closed')::int closed,
        (SELECT count(*) FROM job_postings WHERE first_seen>=$1 AND first_seen<$2)::int jobs`, A),
    q(`SELECT city,count(*)::int n FROM articles WHERE city IS NOT NULL AND published_at>=$1 AND published_at<$2 GROUP BY 1 ORDER BY 2 DESC LIMIT ${top}`, A),
    q(`SELECT c.name,count(*)::int n FROM job_postings j JOIN companies c ON c.id=j.company_id WHERE j.first_seen>=$1 AND j.first_seen<$2 GROUP BY 1 ORDER BY 2 DESC LIMIT ${top}`, A),
    q(`SELECT * FROM expansions WHERE announced_at>=$1 AND announced_at<$2 ORDER BY announced_at DESC LIMIT ${top * 3}`, A),
    q(`SELECT * FROM articles WHERE published_at>=$1 AND published_at<$2 ORDER BY published_at DESC LIMIT ${top * 2}`, A)]);
  const prev = qn === 1 ? [y - 1, 4] : [y, qn - 1], next = qn === 4 ? [y + 1, 1] : [y, qn + 1];
  return (<main className="wrap page"><p><a href="/reports">← All reports</a></p><span className="eyebrow"><i />Quarterly report</span>
    <h1>GCC India · {y} <em>Q{qn}</em></h1>
    <div className="stats">{[["c1", m.opened, "centres opened (detected)"], ["c2", m.expanded, "expansions (detected)"], ["c3", m.closed, "closures (detected)"], ["c4", m.news, "stories tracked"]].map(([c, v, l]) => <div key={l} className={"block " + c}><b>{v}</b><span>{l}</span></div>)}</div>
    <p className="mut">Centre events are detected from headlines and checked by our team over time; see <a href="/methodology">methodology</a>.{new Date() < e && " This quarter is still in progress."}</p>
    <h2>Most-covered cities</h2><ol>{cities.map(c => <li key={c.city}><b>{c.city}</b> — {c.n} {c.n === 1 ? "story" : "stories"}</li>)}</ol>{cities.length === 0 && <p className="mut">No city-tagged coverage this quarter.</p>}
    <h2>Top hiring companies</h2><ol>{cos.map(c => <li key={c.name}><b>{c.name}</b> — {c.n} new India roles</li>)}</ol>{cos.length === 0 && <p className="mut">No tracked job postings in this quarter.</p>}
    <h2>Expansions &amp; launches</h2><ul>{exps.map(x => <li key={x.id}><span className={"ev " + x.event}>{x.event}</span> <a href={x.source_url} target="_blank" rel="nofollow noopener">{clean(x.summary || x.company_name)}</a></li>)}</ul>
    <h2>Headlines</h2><ul>{news.map(a => <li key={a.id}><a href={a.source_url} target="_blank" rel="nofollow noopener">{clean(a.title)}</a> <small className="mut">{a.source_name}</small></li>)}</ul>
    {!p.export && <p className="lock">Showing top {top}. <a href="/pricing">Upgrade to Pro</a> for full rankings.</p>}
    <p className="pager"><a href={`/reports/${prev[0]}/q${prev[1]}`}>← Q{prev[1]} {prev[0]}</a>{(next[0] < new Date().getUTCFullYear() || (next[0] === new Date().getUTCFullYear() && next[1] <= Math.floor(new Date().getUTCMonth() / 3) + 1)) && <a href={`/reports/${next[0]}/q${next[1]}`}>Q{next[1]} {next[0]} →</a>}</p></main>);
}
