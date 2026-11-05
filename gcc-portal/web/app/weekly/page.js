import { q } from "../../lib/db";
import { css } from "../subscribe/styles";
export const dynamic = "force-dynamic";
export const metadata = {
  title: "The GCC Weekly: archive of every issue",
  description: "Every issue of The GCC Weekly, newest first: new and expanded GCCs in India, leadership moves, deals, policy and who is hiring.",
  alternates: { canonical: "/weekly", types: { "application/rss+xml": "/weekly/rss.xml" } },
};
const range = (ws) => { const a = new Date(ws + "T00:00:00Z"), b = new Date(a.getTime() + 6 * 864e5); const f = (d, y) => d.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(y ? { year: "numeric" } : {}), timeZone: "UTC" }); return `${f(a)} – ${f(b, true)}`; };
export default async function Weekly() {
  const rows = await q("SELECT week_start::text ws, stats->>'issue' issue, stats->'headline'->>'title' hl, stats->'numbers' n FROM digests ORDER BY week_start DESC").catch(() => []);
  const base = process.env.SITE_URL || "http://localhost:3000";
  const ld = { "@context": "https://schema.org", "@type": "CollectionPage", name: "The GCC Weekly", url: `${base}/weekly`, description: metadata.description,
    isPartOf: { "@type": "WebSite", name: "GCC Intel India", url: base },
    mainEntity: { "@type": "ItemList", itemListOrder: "https://schema.org/ItemListOrderDescending", numberOfItems: rows.length,
      itemListElement: rows.slice(0, 50).map((d, i) => ({ "@type": "ListItem", position: i + 1, url: `${base}/weekly/${d.ws}`, name: `The GCC Weekly No. ${d.issue}: ${range(d.ws)}` })) } };
  return (<main className="wrap page"><style dangerouslySetInnerHTML={{ __html: css }} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld).replace(/</g, "\\u003c") }} />
    <span className="eyebrow"><i />Every Monday, built from the data</span>
    <h1>The GCC <em>Weekly.</em></h1>
    <p className="prose" style={{ fontSize: 19, maxWidth: 640 }}>New centres, expansions, leadership moves, deals and policy, one issue per week, newest first. <a href="/subscribe">Get it by email</a> or follow the <a href="/weekly/rss.xml">RSS feed</a>.</p>
    {rows.length === 0 && <p className="mut">No issues yet. The first one is built on Monday.</p>}
    <ul className="wk-list">{rows.map(d => (<li key={d.ws}><a className="wk-item" href={`/weekly/${d.ws}`}>
      <span className="wk-no">{d.issue}</span>
      <div><h2>{d.hl || `Issue of ${range(d.ws)}`}</h2><p>{range(d.ws).toUpperCase()}</p></div>
      <div className="wk-stats"><span className="tag">{d.n?.stories ?? 0} stories</span><span className="tag" style={{ background: "var(--lime)" }}>{d.n?.new_centres ?? 0} new</span><span className="tag">{d.n?.expanded ?? 0} expanded</span></div>
    </a></li>))}</ul></main>);
}
