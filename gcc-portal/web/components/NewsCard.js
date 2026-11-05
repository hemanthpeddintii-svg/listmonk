import { ago, clean, external } from "../lib/content";
import "../app/community.css";
const host = (a) => a.source_name?.replace(/^https?:\/\//, "").replace(/\/$/, "") || "GCC Intel";
export default function NewsCard({ a, big, row }) {
  const sc = Number(a.score) || 0, cc = Number(a.comment_count) || 0;
  if (row) return (<article className="nrow"><div className="when">{ago(a.published_at)}</div><div>
    <h3><a href={`/story/${a.id}`}>{clean(a.title)}</a></h3>
    <div className="meta"><span>{host(a)}</span>{a.city && <span>{a.city}</span>}{a.category && a.category !== "other" && <span>{a.category}</span>}
      <span>{cc > 0 ? `${cc} comment${cc === 1 ? "" : "s"}` : "Discuss"}</span>{sc > 0 && <span>▲ {sc}</span>}</div></div></article>);
  return (<article className={"ncard" + (big ? " big" : "")}>
    <div className="ncard-top">{a.city && <span className="tag">{a.city}</span>}<span className="kind">{a.kind}</span></div>
    <h3><a href={`/story/${a.id}`}>{clean(a.title)}</a></h3>
    <div className="ncard-foot">
      <span>{host(a)} · {ago(a.published_at)}</span>
      <span className="ncard-stats">
        {sc > 0 && <span className="sc">▲ {sc}</span>}
        <span>{cc > 0 ? `${cc} comment${cc === 1 ? "" : "s"}` : "Discuss"}</span>
        {external(a) && a.source_url && <a className="ncard-src" href={a.source_url} target="_blank" rel="nofollow noopener" aria-label={`Read at ${host(a)} (opens in a new tab)`}>↗ source</a>}
      </span></div></article>);
}
