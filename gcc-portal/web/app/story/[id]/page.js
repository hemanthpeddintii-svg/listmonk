import { notFound } from "next/navigation";
import { q } from "../../../lib/db";
import { ago, clean, external } from "../../../lib/content";
import Comments from "../../../components/Comments";
import FollowButton from "../../../components/FollowButton";
import VoteButton from "../../../components/VoteButton";
import "../../community.css";
export const dynamic = "force-dynamic";

const load = async (id) => (Number.isInteger(id) && id > 0 && id < 2 ** 31
  ? (await q("SELECT a.*, c.name AS company_name FROM articles a LEFT JOIN companies c ON c.id=a.company_id WHERE a.id=$1", [id]))[0] : null);
const ymd = (d) => (d ? new Date(d).toISOString().slice(0, 10) : "");
const site = () => (process.env.SITE_URL || "http://localhost:3000").replace(/\/$/, "");
const host = (a) => a.source_name?.replace(/^https?:\/\//, "").replace(/\/$/, "") || "GCC Intel";

export async function generateMetadata({ params }) {
  const a = await load(Number(params.id));
  if (!a) return { title: "Story not found" };
  const title = clean(a.title);
  const desc = (!external(a) && a.summary) || `${[a.city, host(a)].filter(Boolean).join(" · ")}: discussion and related coverage of this GCC story. We link to the original report.`;
  return { title, description: desc.slice(0, 200), alternates: { canonical: `/story/${a.id}` },
    openGraph: { title, description: desc.slice(0, 200), type: "article", publishedTime: a.published_at ? new Date(a.published_at).toISOString() : undefined, url: `/story/${a.id}` } };
}

export default async function Story({ params }) {
  const a = await load(Number(params.id));
  if (!a) notFound();
  const ext = external(a);
  const title = clean(a.title);
  const related = await q(`SELECT id,title,city,source_name,published_at FROM articles
      WHERE id<>$1 AND (($2::int IS NOT NULL AND company_id=$2) OR ($3::text IS NOT NULL AND city=$3) OR ($4::text IS NOT NULL AND category=$4))
      ORDER BY published_at DESC NULLS LAST LIMIT 6`, [a.id, a.company_id || null, a.city || null, a.category || null]);
  const ld = {
    "@context": "https://schema.org", "@type": "NewsArticle", headline: title.slice(0, 110),
    datePublished: a.published_at ? new Date(a.published_at).toISOString() : undefined,
    mainEntityOfPage: `${site()}/story/${a.id}`,
    ...(ext && a.source_url ? { url: a.source_url, isBasedOn: a.source_url } : { url: `${site()}/story/${a.id}` }),
    author: { "@type": "Organization", name: ext ? host(a) : "GCC Intel India" },
    publisher: { "@type": "Organization", name: ext ? host(a) : "GCC Intel India" },
    isAccessibleForFree: true, inLanguage: "en-IN",
    ...(a.city ? { contentLocation: { "@type": "Place", name: a.city } } : {}),
    ...(a.company_name ? { about: { "@type": "Organization", name: a.company_name } } : {}),
    commentCount: a.comment_count || 0, interactionStatistic: { "@type": "InteractionCounter", interactionType: "https://schema.org/LikeAction", userInteractionCount: a.score || 0 } };
  const tags = (a.tags || []).filter(Boolean);
  return (<main className="wrap page story">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld).replace(/</g, "\\u003c") }} />
    <p><a className="story-back" href="/news">← All news</a></p>
    <div className="story-meta">
      <span>{a.kind}</span>
      {a.city && <a className="tag" href={`/cities/${encodeURIComponent(a.city)}`}>{a.city}</a>}
      {a.category && <span className="tag" style={{ background: "var(--lime)" }}>{a.category}</span>}
      {tags.map(t => <span key={t} className="tag" style={{ background: "#fff" }}>{t}</span>)}
    </div>
    <h1 className="story-h">{title}</h1>
    <div className="story-meta"><span>{host(a)}</span><span className="mut">·</span><time dateTime={ymd(a.published_at)}>{ymd(a.published_at)}</time>{ago(a.published_at) !== ymd(a.published_at) && <span className="mut">({ago(a.published_at)})</span>}
      {a.company_name && <><span className="mut">·</span><a href={`/companies/${a.company_id}`}>{a.company_name}</a></>}</div>

    <div className="story-cta">
      {ext && a.source_url && <a className="btn src" href={a.source_url} target="_blank" rel="nofollow noopener">Read at {host(a)} ↗</a>}
      <VoteButton articleId={a.id} score={a.score || 0} />
      <a className="vote" href="#discussion" style={{ paddingLeft: 16 }}><b>{a.comment_count || 0}</b><span className="vote-lbl">comments</span></a>
    </div>
    {ext && <p className="story-note">This is a headline we found, not our article. The reporting is {host(a)}'s; we link to it and keep the discussion here.</p>}

    <div className="story-follow"><span className="lbl">Follow for your feed</span>
      {a.city && <FollowButton kind="city" value={a.city} label={a.city} next={`/story/${a.id}`} />}
      {a.company_id && <FollowButton kind="company" value={a.company_id} label={a.company_name} next={`/story/${a.id}`} />}
      {a.category && <FollowButton kind="topic" value={a.category} label={a.category} next={`/story/${a.id}`} />}
      {!a.city && !a.company_id && !a.category && <a className="fol" href="/following"><span className="fol-plus">+</span> Pick cities and topics</a>}
    </div>

    <div className="story-cols">
      <div>
        {!ext && <div className="story-body">
          {a.summary && a.summary !== a.body && <p style={{ fontFamily: "var(--serif)", fontSize: 24, lineHeight: 1.35 }}>{a.summary}</p>}
          {a.body.split(/\n\n+/).map((p, i) => <p key={i}>{p}</p>)}</div>}
        <Comments targetType="article" targetId={a.id} next={`/story/${a.id}`}
          emptyPrompt={`Be the first to add context. What does this mean for hiring${a.city ? ` in ${a.city}` : a.company_name ? ` at ${a.company_name}` : " at GCCs in India"}?`} />
      </div>
      <aside className="story-side"><div className="rel"><h3>Related stories</h3>
        {related.length ? <ul>{related.map(r => <li key={r.id}><a href={`/story/${r.id}`}>{clean(r.title)}</a><small>{[r.city, host(r), ago(r.published_at)].filter(Boolean).join(" · ")}</small></li>)}</ul>
          : <p className="none">Nothing else tagged to the same city, company or topic yet.</p>}
      </div></aside>
    </div>
  </main>);
}
