import { q } from "../lib/db";
import { getUser } from "../lib/auth";
import { toggleFollow } from "../app/actions-community";
import "../app/community.css";

const defNext = (kind, value) => kind === "company" ? `/companies/${value}` : kind === "city" ? `/cities/${encodeURIComponent(value)}` : "/following";

// Drop-in: <FollowButton kind="company" value={id} label="Infosys" />   kind: company | city | topic
// Server component with a plain <form>, so it works without client JS.
export default async function FollowButton({ kind, value, label, next }) {
  const v = String(value);
  const u = await getUser();
  const on = u ? (await q("SELECT 1 FROM follows WHERE user_id=$1 AND kind=$2 AND value=$3", [u.id, kind, v])).length > 0 : false;
  const noun = label || v;
  const verb = { company: "company", city: "city", topic: "topic" }[kind];
  if (!u) return <a className="fol" href={"/login?next=" + encodeURIComponent(next || defNext(kind, v))} title={`Log in to follow this ${verb}`}><span className="fol-plus">+</span> Follow {noun}</a>;
  return (
    <form action={toggleFollow} className="fol-form">
      <input type="hidden" name="kind" value={kind} /><input type="hidden" name="value" value={v} /><input type="hidden" name="next" value={next || defNext(kind, v)} />
      <button className={"fol" + (on ? " on" : "")} aria-pressed={on} title={on ? `Stop following ${noun}` : `Follow ${noun}: new stories show up in your feed`}>
        <span className="fol-plus">{on ? "✓" : "+"}</span> {on ? "Following" : "Follow"} {noun}</button>
    </form>);
}
