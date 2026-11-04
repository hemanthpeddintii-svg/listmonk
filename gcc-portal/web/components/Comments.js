import { q } from "../lib/db";
import { getUser } from "../lib/auth";
import { ago } from "../lib/content";
import { displayName } from "../lib/community";
import { deleteComment, reportComment } from "../app/actions-community";
import CommentForm from "./CommentForm";
import "../app/community.css";

const defNext = (t, id) => t === "company" ? `/companies/${id}` : t === "article" ? `/story/${id}` : "/expansions";

function Item({ c, u, replies = [], type, id, next }) {
  const mine = u && u.id === c.user_id, admin = u?.role === "admin";
  const hidden = c.reports >= 3;
  const gone = c.deleted;
  return (
    <li className={"cm" + (c.parent_id ? " reply" : "")} id={`c${c.id}`}>
      {gone ? <p className="cm-gone">Deleted by the author.</p>
        : hidden && !admin ? <p className="cm-gone">Hidden after reports from readers.</p>
        : (<>
          <div className="cm-head"><b>{c.author}</b>{c.role === "admin" && <span className="tag cm-staff">GCC Intel</span>}
            <span className="mut">{ago(c.created_at)}</span>{hidden && <span className="cm-flag">hidden · {c.reports} reports</span>}</div>
          <p className={"cm-body" + (hidden ? " dim" : "")}>{c.body}</p>
          <div className="cm-acts">
            {u && !c.parent_id && <details className="cm-reply"><summary>Reply</summary>
              <CommentForm targetType={type} targetId={id} parentId={c.id} label="Post reply" placeholder={`Reply to ${c.author}`} /></details>}
            {u && !mine && <form action={reportComment}><input type="hidden" name="id" value={c.id} /><input type="hidden" name="next" value={next} /><button className="cm-link" title="Flag this comment. Three reports hide it.">Report</button></form>}
            {(mine || admin) && <form action={deleteComment}><input type="hidden" name="id" value={c.id} /><button className="cm-link danger">Delete</button></form>}
          </div></>)}
      {replies.length > 0 && <ul className="cm-list">{replies.map(r => <Item key={r.id} c={r} u={u} type={type} id={id} next={next} />)}</ul>}
    </li>);
}

// Drop-in: <Comments targetType="article|company|expansion" targetId={id} noun="Infosys" city="Pune" />
export default async function Comments({ targetType, targetId, next, emptyPrompt, noun }) {
  const u = await getUser();
  const nx = next || defNext(targetType, targetId);
  const rows = await q(`SELECT c.id,c.user_id,c.parent_id,c.body,c.deleted,c.reports,c.created_at,x.name,x.email,x.role
      FROM comments c JOIN users x ON x.id=c.user_id WHERE c.target_type=$1 AND c.target_id=$2 ORDER BY c.created_at ASC LIMIT 600`, [targetType, targetId]);
  rows.forEach(r => { r.author = displayName(r); delete r.email; });
  const kids = new Map();
  for (const r of rows) if (r.parent_id) (kids.get(r.parent_id) || kids.set(r.parent_id, []).get(r.parent_id)).push(r);
  const visibleKid = (r) => !r.deleted;            // a deleted reply leaves no placeholder
  const tops = rows.filter(r => !r.parent_id).map(r => ({ ...r, replies: (kids.get(r.id) || []).filter(visibleKid) }))
    .filter(r => !r.deleted || r.replies.length);  // a deleted top comment stays only to hold its replies
  const live = rows.filter(r => !r.deleted && r.reports < 3).length;
  const prompt = emptyPrompt || `Be the first to add context. What does this mean for ${noun ? `hiring at ${noun}` : "GCC hiring in India"}?`;
  return (
    <section className="cm-wrap" id="discussion" aria-label="Discussion">
      <h2 className="cm-title">Discussion <span className="cm-n">{live}</span></h2>
      {u ? <CommentForm targetType={targetType} targetId={targetId} placeholder="Add context: what you know, what it changes, what to watch. Plain text, 2000 characters." />
        : (<div className="cm-login"><p><b>Join the discussion.</b> Reading is open; posting needs a free account.</p>
            <a className="btn" href={"/login?next=" + encodeURIComponent(nx + "#discussion")}>Log in to join <span>→</span></a>
            <a className="cm-alt" href="/signup">or create an account</a></div>)}
      {tops.length === 0 ? <p className="cm-empty">{prompt}</p>
        : <ul className="cm-list top">{tops.map(c => <Item key={c.id} c={c} u={u} replies={c.replies} type={targetType} id={targetId} next={nx} />)}</ul>}
    </section>);
}
