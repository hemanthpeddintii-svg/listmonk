import { q } from "../lib/db";
import { getUser } from "../lib/auth";
import { toggleVote } from "../app/actions-community";
import "../app/community.css";

// <VoteButton articleId={id} score={a.score} />  One upvote per user, click again to take it back.
export default async function VoteButton({ articleId, score = 0, next }) {
  const u = await getUser();
  const on = u ? (await q("SELECT 1 FROM votes WHERE user_id=$1 AND article_id=$2", [u.id, articleId])).length > 0 : false;
  const inner = (<><span className="vote-arrow">▲</span><b>{score}</b><span className="vote-lbl">{on ? "Upvoted" : "Upvote"}</span></>);
  if (!u) return <a className="vote" href={"/login?next=" + encodeURIComponent(next || `/story/${articleId}`)} title="Log in to upvote">{inner}</a>;
  return (
    <form action={toggleVote} className="vote-form">
      <input type="hidden" name="articleId" value={articleId} /><input type="hidden" name="next" value={next || `/story/${articleId}`} />
      <button className={"vote" + (on ? " on" : "")} aria-pressed={on} title={on ? "Remove your upvote" : "Upvote this story"}>{inner}</button>
    </form>);
}
