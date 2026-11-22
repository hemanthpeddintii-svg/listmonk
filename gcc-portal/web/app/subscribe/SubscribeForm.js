"use client";
import { useFormState, useFormStatus } from "react-dom";
import { subscribe } from "../actions-subscribe";

function Go({ label }) { const { pending } = useFormStatus(); return <button className="btn" disabled={pending}>{pending ? "Sending…" : label} <span>→</span></button>; }

export default function SubscribeForm({ topics = [], cities = [], compact = false }) {
  const [s, act] = useFormState(subscribe, null);
  if (s?.ok) return (<div className="sub-done"><b>{s.ok}</b>
    {s.confirmUrl && <p><a className="btn" href={s.confirmUrl}>Confirm now <span>→</span></a><br /><small className="mut">{s.confirmUrl}</small></p>}</div>);
  return (<form action={act} className="sub-form">
    {/* honeypot: hidden from people, irresistible to bots */}
    <div aria-hidden="true" style={{ position: "absolute", left: "-9999px", width: 1, height: 1, overflow: "hidden" }}>
      <label>Website<input name="website" tabIndex={-1} autoComplete="off" /></label></div>
    <div className="sub-row"><input type="email" name="email" required placeholder="you@company.com" autoComplete="email" aria-label="Email address" maxLength={254} /><Go label="Subscribe" /></div>
    {!compact && (<>
      <fieldset><legend>Topics <small className="mut">(none ticked means everything)</small></legend>
        <div className="sub-chips">{topics.map(([k, l]) => <label key={k} className="sub-chip"><input type="checkbox" name="topics" value={k} /><span>{l}</span></label>)}</div></fieldset>
      <fieldset><legend>Cities <small className="mut">(none ticked means all)</small></legend>
        <div className="sub-chips">{cities.map(c => <label key={c} className="sub-chip"><input type="checkbox" name="cities" value={c} /><span>{c}</span></label>)}</div></fieldset></>)}
    {s?.error && <p className="err" role="alert">{s.error}</p>}
  </form>);
}
