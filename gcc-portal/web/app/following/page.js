import { q } from "../../lib/db";
import { requireUser } from "../../lib/auth";
import { CITY_LIST, ago, clean } from "../../lib/content";
import { TOPICS, getFollows, getFeed, getFeedCount } from "../../lib/community";
import FollowButton from "../../components/FollowButton";
import "../community.css";
export const dynamic = "force-dynamic";
export const metadata = { title: "Following", robots: { index: false } };

export default async function Following() {
  const u = await requireUser();
  const f = await getFollows(u.id);
  const [feed, week, comps] = await Promise.all([
    getFeed(u.id, 40), getFeedCount(u.id, 7),
    f.company.length ? q("SELECT id,name FROM companies WHERE id = ANY($1::int[])", [f.company.filter(v => /^\d+$/.test(v)).map(Number)]) : []]);
  const cname = new Map(comps.map(c => [String(c.id), c.name]));
  return (<main className="wrap page"><span className="eyebrow"><i />Your feed</span>
    <h1>What you <em>follow.</em></h1>
    <div className="fcounts">
      <div className="fcount"><b>{f.company.length}</b><span>Companies</span></div>
      <div className="fcount"><b>{f.city.length}</b><span>Cities</span></div>
      <div className="fcount"><b>{f.topic.length}</b><span>Topics</span></div>
      <div className="fcount" style={{ background: "var(--lime)" }}><b>{week}</b><span>New this week</span></div></div>

    <h2>Newest from your follows</h2>
    {f.total === 0 ? <p className="mut" style={{ maxWidth: "58ch" }}>Nothing followed yet. Pick a city or topic below, or hit Follow on any company page or story, and matching headlines land here newest first.</p>
      : feed.length === 0 ? <p className="mut" style={{ maxWidth: "58ch" }}>No stories match yet. Company follows match stories we have tagged to that company; topic follows fill in as stories get categorised.</p>
      : <ul className="feed">{feed.map(a => <li key={a.id}>
          <a className="h" href={`/story/${a.id}`}>{clean(a.title)}</a>
          <span className="s">{a.score > 0 && `▲ ${a.score} · `}{a.comment_count} comment{a.comment_count === 1 ? "" : "s"}</span>
          <span className="m"><span>{a.source_name || "GCC Intel"}</span><span>{ago(a.published_at)}</span>{a.city && <span>{a.city}</span>}{a.company_name && <span>{a.company_name}</span>}{a.category && <span>{a.category}</span>}</span></li>)}</ul>}

    <h2>Cities</h2>
    <div className="fol-grid">{CITY_LIST.map(c => <FollowButton key={c} kind="city" value={c} label={c} next="/following" />)}</div>
    <h2>Topics</h2>
    <div className="fol-grid">{TOPICS.map(t => <FollowButton key={t} kind="topic" value={t} label={t} next="/following" />)}</div>
    <h2>Companies</h2>
    {f.company.length > 0 ? <ul className="fol-list">{f.company.map(id => <li key={id}><FollowButton kind="company" value={id} label={cname.get(id) || `#${id}`} next="/following" /></li>)}</ul>
      : <p className="mut">None yet. Open a company in the <a href="/companies">explorer</a> and follow it, or follow the company named on a story.</p>}
  </main>);
}
