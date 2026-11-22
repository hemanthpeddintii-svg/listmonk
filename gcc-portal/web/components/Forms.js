"use client";
import { useFormState, useFormStatus } from "react-dom";
function Submit({ children }) { const { pending } = useFormStatus(); return <button className="btn" disabled={pending}>{pending ? "…" : children}</button>; }
export function ActionForm({ action, children, submit, className = "col" }) {
  const [s, fn] = useFormState(action, null);
  return (<form action={fn} className={className}>{children}
    <Submit>{submit}</Submit>
    {s?.error && <span className="err">{s.error}</span>}{s?.ok && <span className="ok">{s.ok}</span>}</form>);
}
