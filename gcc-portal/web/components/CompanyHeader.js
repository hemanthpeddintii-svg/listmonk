"use client";
import { useState } from "react";

// Logo tile: Wikimedia Commons logo when we have one, ink-on-lilac initials otherwise (also if the image fails to load).
const initials = (n = "") => n.replace(/\(.*?\)/g, "").split(/[\s&.\-]+/).filter(w => /[A-Za-z0-9]/.test(w) && !/^(the|of|and|india|inc|corp|group)$/i.test(w)).slice(0, 2).map(w => w[0].toUpperCase()).join("") || "GC";
const tint = (n = "") => ["#cdbdff", "#d7f25a", "#ffd9cc", "#ffffff"][[...n].reduce((s, ch) => s + ch.charCodeAt(0), 0) % 4];

function Logo({ name, src }) {
  const [bad, setBad] = useState(false);
  if (src && !bad) return <span className="co-logo has"><img src={src} alt={`${name} logo`} width={72} height={72} loading="eager" onError={() => setBad(true)} /></span>;
  return <span className="co-logo" style={{ background: tint(name) }} aria-hidden="true">{initials(name)}</span>;
}

const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };

// Server-rendered action buttons (Save / Follow) arrive as `actions`.
export default function CompanyHeader({ c, actions }) {
  const cities = c.india_cities || [];
  return (
    <header className="co-head">
      <Logo name={c.parent_company || c.name} src={c.logo_url} />
      <div className="co-id">
        <div className="co-eyebrow">
          {c.parent_company && <span>Parent: <b>{c.parent_company}</b></span>}
          {c.hq_country && <span>HQ {c.hq_country}</span>}
          {c.industry && <span>{c.industry}</span>}
        </div>
        <h1>{c.name}</h1>
        {cities.length > 0 && <p className="co-cities">{cities.map(x => <a key={x} className="tag" href={`/cities/${encodeURIComponent(x)}`}>{x}</a>)}</p>}
        {c.description && <p className="co-desc">{c.description}</p>}
        <p className="co-links">
          {c.website && <a href={c.website} target="_blank" rel="nofollow noopener">{host(c.website)} ↗</a>}
          {c.wikipedia_url && <a href={c.wikipedia_url} target="_blank" rel="nofollow noopener">Wikipedia ↗</a>}
          {c.ticker && <span className="co-tick" title="Stock listing of the parent">{c.ticker}</span>}
        </p>
      </div>
      <div className="co-actions">{actions}</div>
    </header>
  );
}
