"use client";
import { useEffect, useState, useCallback } from "react";
const WHO = ["Selling to GCCs", "Hiring from GCCs", "Researching the market", "Investing / advising"];
const letter = (i) => String.fromCharCode(65 + i);

export default function Finder({ cities, industries }) {
  const [step, setStep] = useState(0), [ans, setAns] = useState({}), [count, setCount] = useState(null), [dir, setDir] = useState(1);
  const lists = [WHO, ["Anywhere", ...cities.slice(0, 7)], ["Any industry", ...industries.slice(0, 7)]];
  const keys = ["who", "city", "industry"];
  const titles = ["First things first. What brings you here?", "Which city matters most to you?", "And which industry?"];

  const pick = useCallback((i) => {
    const list = lists[step]; if (i >= list.length) return;
    const val = (step > 0 && i === 0) ? "" : list[i];
    setAns(a => ({ ...a, [keys[step]]: val })); setDir(1); setTimeout(() => setStep(s => s + 1), 260);
  }, [step, cities, industries]); // eslint-disable-line
  useEffect(() => {
    const h = (e) => {
      if (e.target.closest?.("input,textarea,select")) return;
      if (step < 3 && /^[a-h]$/i.test(e.key)) pick(e.key.toUpperCase().charCodeAt(0) - 65);
      if (e.key === "Backspace" && step > 0) { setDir(-1); setStep(s => s - 1); }
      if (e.key === "Enter" && step === 3) location.href = href;
    };
    addEventListener("keydown", h); return () => removeEventListener("keydown", h);
  });
  const params = new URLSearchParams(Object.entries({ city: ans.city, industry: ans.industry }).filter(([, v]) => v));
  const href = "/companies" + (params.toString() ? "?" + params : "");
  useEffect(() => { if (step === 3) { setCount(null); fetch("/api/count?" + params).then(r => r.json()).then(d => setCount(d.n)).catch(() => setCount(0)); } }, [step]); // eslint-disable-line

  return (<div className="finder" id="finder">
    <div className="finder-bar"><i style={{ width: `${(Math.min(step, 3) / 3) * 100}%` }} /></div>
    <div className="finder-top"><span>{step < 3 ? `${step + 1} → 3` : "Done ✓"}</span>
      {step > 0 && <button onClick={() => { setDir(-1); setStep(step - 1); }}>← back</button>}</div>
    <div key={step} className={"finder-step " + (dir > 0 ? "in-up" : "in-down")}>
      {step < 3 ? (<>
        <h3>{titles[step]}</h3>
        <div className="opts">{lists[step].map((o, i) => (
          <button key={o} className={"opt" + (ans[keys[step]] === o ? " on" : "")} style={{ animationDelay: `${i * 55}ms` }} onClick={() => pick(i)}>
            <kbd>{letter(i)}</kbd><span>{o}</span></button>))}</div>
        <p className="hint">Press the letter key to choose</p></>) : (<>
        <h3>{count === null ? "Searching…" : count === 0 ? "No match yet — but the list grows every 3 days." : <>We found <em className="big">{count}</em> {count === 1 ? "company" : "companies"} for you.</>}</h3>
        <div className="opts row-opts"><a className="btn big-btn" href={href}>Show me <span>→</span></a>
          <button className="btn ghost-dark" onClick={() => { setStep(0); setAns({}); }}>Start over</button></div>
        <p className="hint">Press Enter ↵</p></>)}
    </div></div>);
}
