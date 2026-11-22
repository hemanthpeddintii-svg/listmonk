"use client";
import { useState, useRef } from "react";
import { useFormState, useFormStatus } from "react-dom";
function Go({ last, label }) { const { pending } = useFormStatus(); return <button type="submit" className="btn">{pending ? "…" : last ? label : "OK"} <span>↵</span></button>; }
// One field per screen, Typeform-style. Enter advances; the last Enter submits.
export default function StepForm({ action, fields, submit, hidden = {} }) {
  const [s, fn] = useFormState(action, null); const [i, setI] = useState(0); const [bad, setBad] = useState(""); const form = useRef(null);
  const f = fields[i], last = i === fields.length - 1;
  const next = (e) => {
    const inp = form.current.elements[f.name]; const val = inp.value.trim();
    const invalid = (f.required && !val) || (f.type === "email" && val && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(val)) || (f.minLength && val.length < f.minLength);
    if (!last) { e.preventDefault(); if (invalid) { setBad(f.msg || "Please fill this in."); return; } setBad(""); setI(i + 1); setTimeout(() => form.current.elements[fields[i + 1].name]?.focus(), 60); }
    else if (invalid) { e.preventDefault(); setBad(f.msg || "Please fill this in."); }
  };
  return (<form ref={form} action={fn} onSubmit={next} noValidate className="stepform">
    {Object.entries(hidden).map(([k, v]) => <input key={k} type="hidden" name={k} value={v} />)}
    <div className="finder-bar"><i style={{ width: `${((i + 1) / fields.length) * 100}%` }} /></div>
    {fields.map((x, n) => (<div key={x.name} className={"sf-field" + (n === i ? " on" : "")} aria-hidden={n !== i}>
      <label htmlFor={x.name}><span className="num">{n + 1}→</span> {x.label}</label>
      <input id={x.name} name={x.name} type={x.type || "text"} placeholder={x.placeholder} autoFocus={n === 0} tabIndex={n === i ? 0 : -1} autoComplete={x.auto} />
    </div>))}
    <div className="sf-actions"><Go last={last} label={submit} />{i > 0 && <button type="button" className="linkbtn" onClick={() => setI(i - 1)}>← back</button>}</div>
    {(bad || s?.error) && <p className="err">{bad || s.error}</p>}
  </form>);
}
