import { ago, clean, href, external } from "../lib/content";
export default function NewsCard({ a, big }) {
  return (<a className={"ncard" + (big ? " big" : "")} href={href(a)} {...(external(a) ? { target: "_blank", rel: "nofollow noopener" } : {})}>
    <div className="ncard-top">{a.city && <span className="tag">{a.city}</span>}<span className="kind">{a.kind}</span></div>
    <h3>{clean(a.title)}</h3>
    <div className="ncard-foot"><span>{a.source_name?.replace(/^https?:\/\//, "").replace(/\/$/, "") || "GCC Intel"}</span><span>{ago(a.published_at)} {external(a) && "↗"}</span></div></a>);
}
