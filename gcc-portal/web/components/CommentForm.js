"use client";
import { useEffect, useRef, useState } from "react";
import { useFormState, useFormStatus } from "react-dom";
import { postComment } from "../app/actions-community";
import "../app/community.css";

function Send({ label }) { const { pending } = useFormStatus(); return <button className="btn cm-send" disabled={pending}>{pending ? "Posting…" : label}</button>; }

export default function CommentForm({ targetType, targetId, parentId = null, placeholder, label = "Post comment", autoFocus = false }) {
  const [s, act] = useFormState(postComment, null);
  const [len, setLen] = useState(0);
  const form = useRef(null);
  useEffect(() => {
    if (s?.ok) { form.current?.reset(); setLen(0); const d = form.current?.closest("details"); if (d) d.open = false; }
  }, [s]);
  return (
    <form ref={form} action={act} className="cm-form">
      <input type="hidden" name="targetType" value={targetType} /><input type="hidden" name="targetId" value={targetId} />
      {parentId && <input type="hidden" name="parentId" value={parentId} />}
      <textarea name="body" required maxLength={2000} rows={parentId ? 3 : 4} autoFocus={autoFocus} placeholder={placeholder}
        aria-label={parentId ? "Your reply" : "Your comment"} onChange={e => setLen(e.target.value.length)} />
      <div className="cm-bar">
        <span className={"cm-count" + (len > 1800 ? " warn" : "")}>{len}/2000 · plain text only</span>
        <Send label={label} />
      </div>
      {s?.error && <p className="err cm-err" role="alert">{s.error}</p>}
      {s?.ok && <p className="ok cm-err" role="status">Posted.</p>}
    </form>);
}
