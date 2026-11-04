import { notFound } from "next/navigation";
import { q } from "../../../lib/db";
import { bodyOf } from "../../../lib/rss";
import SubscribeForm from "../../subscribe/SubscribeForm";
import { css } from "../../subscribe/styles";
export const dynamic = "force-dynamic";

const valid = (s) => /^\d{4}-\d{2}-\d{2}$/.test(s) && new Date(s + "T00:00:00Z").getUTCDay() === 1 && !isNaN(new Date(s));
const load = async (ws) => valid(ws) ? (await q("SELECT week_start::text ws, title, html, stats, created_at FROM digests WHERE week_start=$1", [ws]))[0] : null;

export async function generateMetadata({ params }) {
  const d = await load(params.weekStart);
  if (!d) return { title: "Issue not found" };
  const n = d.stats?.numbers || {};
  const description = `${d.stats?.headline?.title ? d.stats.headline.title + ". " : ""}${n.stories ?? 0} stories, ${n.new_centres ?? 0} new centres and ${n.expanded ?? 0} expansions in India's GCC sector.`;
  return { title: d.title, description, alternates: { canonical: `/weekly/${d.ws}` },
    openGraph: { title: d.title, description, type: "article", url: `/weekly/${d.ws}` } };
}

export default async function Issue({ params }) {
  const d = await load(params.weekStart);
  if (!d) notFound();
  const [prev] = await q("SELECT week_start::text ws, stats->>'issue' issue FROM digests WHERE week_start<$1 ORDER BY week_start DESC LIMIT 1", [d.ws]);
  const [next] = await q("SELECT week_start::text ws, stats->>'issue' issue FROM digests WHERE week_start>$1 ORDER BY week_start ASC LIMIT 1", [d.ws]);
  const body = bodyOf(d.html, "").replace(/\{\{PREFS_URL\}\}/g, "/subscribe").replace(/\{\{UNSUB_URL\}\}/g, "/subscribe");
  const base = process.env.SITE_URL || "http://localhost:3000";
  const end = new Date(Date.parse(d.ws + "T00:00:00Z") + 7 * 864e5).toISOString().slice(0, 10);
  const ld = { "@context": "https://schema.org", "@type": "NewsArticle", headline: d.title, url: `${base}/weekly/${d.ws}`, mainEntityOfPage: `${base}/weekly/${d.ws}`,
    datePublished: `${end}T01:30:00Z`, dateModified: new Date(d.created_at).toISOString(), inLanguage: "en-IN", articleSection: "Global Capability Centers",
    description: d.stats?.headline?.title || undefined,
    author: { "@type": "Organization", name: "GCC Intel India" }, publisher: { "@type": "Organization", name: "GCC Intel India", url: base },
    isPartOf: { "@type": "CreativeWorkSeries", name: "The GCC Weekly", url: `${base}/weekly` } };
  const crumbs = { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: base }, { "@type": "ListItem", position: 2, name: "The GCC Weekly", item: `${base}/weekly` },
    { "@type": "ListItem", position: 3, name: d.title, item: `${base}/weekly/${d.ws}` }] };
  const j = (o) => JSON.stringify(o).replace(/</g, "\\u003c");
  return (<main className="wrap page"><style dangerouslySetInnerHTML={{ __html: css }} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: j(ld) }} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: j(crumbs) }} />
    <div className="issue-nav" style={{ marginBottom: 6 }}><a href="/weekly">← All issues</a><a href="/weekly/rss.xml">RSS</a></div>
    <article className="issue" dangerouslySetInnerHTML={{ __html: body }} />
    <div className="issue-nav">{prev ? <a href={`/weekly/${prev.ws}`}>← No. {prev.issue}</a> : <span />}{next ? <a href={`/weekly/${next.ws}`}>No. {next.issue} →</a> : <span />}</div>
    <section className="issue-cta"><h2>Get the next one on Monday.</h2><p>Free, one email a week, unsubscribe in one click.</p>
      <SubscribeForm compact /><p style={{ margin: "12px 0 0", fontSize: 13 }}><a href="/subscribe" style={{ color: "var(--paper)" }}>Choose topics and cities</a></p></section>
  </main>);
}
