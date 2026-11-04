import { homeData, issueMeta, cat, HUBS } from "../lib/stats";
import { q } from "../lib/db";
import { clean, ago } from "../lib/content";
import IndiaMap from "../components/IndiaMap";
import Finder from "../components/Finder";
import Reveal from "../components/Reveal";
import CountUp from "../components/CountUp";
import NewsCard from "../components/NewsCard";
import { ActionForm } from "../components/Forms";
import { captureLead } from "./actions";
export const dynamic = "force-dynamic";
const CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai"];

export default async function Home() {
  const d = await homeData(), c = d.c, iss = issueMeta();
  const dbCities = (await q("SELECT DISTINCT unnest(india_cities) c FROM companies ORDER BY 1").catch(() => [])).map(r => r.c);
  const inds = (await q("SELECT industry i FROM companies WHERE industry IS NOT NULL GROUP BY 1 ORDER BY count(*) DESC").catch(() => [])).map(r => r.i);
  const [moves, deals, sample] = await Promise.all([cat("leadership", 5), cat("funding", 5),
    q("SELECT name,parent_company,industry,india_cities FROM companies ORDER BY random() LIMIT 6").catch(() => [])]);
  const headlines = d.secondary.map(a => clean(a.title));
  const maxM = Math.max(1, ...d.months.map(m => m.n));
  const lead = d.lead || d.secondary[0];
  const doors = [
    { tag: "I sell to GCCs", h: "Know who just opened, who is hiring, who got the new head.", n: c.opened30 ?? 0, l: "centres opened or expanded, last 30 days", to: "/expansions", cta: "Open the tracker" },
    { tag: "I hire from GCCs", h: "See which centres are hiring right now, city by city.", n: c.jobs ?? 0, l: "live India roles tracked", to: "/jobs", cta: "See live roles" },
    { tag: "I invest or advise", h: "Quarter-by-quarter record, policy by state, deals as they happen.", n: c.deals30 ?? 0, l: "ecosystem deals, last 30 days", to: "/reports", cta: "Read the reports" }];
  return (<main>
    <div className="mast"><div className="wrap mast-in"><span>VOL. 01 · ISSUE {iss.issue}</span><span>{iss.date}</span><span className="mast-hide">BENGALURU · HYDERABAD · PUNE · CHENNAI · NCR · MUMBAI</span><span>NEWS DAILY · DEEP REFRESH WEEKLY</span></div></div>

    <section className="hero"><IndiaMap stats={d.stats} events={d.events} />
      <div className="wrap" style={{ width: "100%" }}><div className="hero-copy">
        <div className="eyebrow"><i />The daily record of India&apos;s capability-center boom</div>
        <h1><span className="line"><span>Global firms are</span></span><span className="line"><span>building <em>India&apos;s</em></span></span><span className="line"><span>next economy.</span></span></h1>
        <p className="lead">We track every one of them. <b>{(c.companies ?? 0).toLocaleString("en-IN")}</b> GCCs, <b>{(c.stories ?? 0).toLocaleString("en-IN")}</b> stories from the last six months, openings, hires, deals and policy — newest first.</p>
        <div className="cta"><a className="btn" href="#doors">Why you&apos;re here <span>↓</span></a><a className="btn ghost" href="/news">Read today&apos;s news</a></div>
        <p className="citylinks">{HUBS.slice(0, 6).map(x => <a key={x} href={`/cities/${encodeURIComponent(x)}`}>{x}</a>)}</p>
      </div></div></section>

    <div className="ticker-clip"><div className="ticker"><div className="ticker-track">{[...headlines, ...headlines].map((n, i) => <span key={i}>{n} <b>✦</b> </span>)}</div></div></div>

    <div className="wrap">
      <section className="section" id="doors"><Reveal><span className="eyebrow">Why this exists</span>
        <h2>Every week a multinational opens a centre in India. <em>Almost nobody is keeping the record.</em></h2>
        <p className="deck">Announcements are scattered across a hundred outlets, LinkedIn posts and state press notes. We collect them, sort them, and tell you what changed. Pick your door.</p></Reveal>
        <div className="doors">{doors.map((x, i) => (<Reveal key={x.tag} delay={i * 110}><a className={"door d" + i} href={x.to}><span className="door-tag">{x.tag}</span><h3>{x.h}</h3>
          <b className="door-n"><CountUp to={x.n} /></b><span className="door-l">{x.l}</span><span className="door-cta">{x.cta} →</span></a></Reveal>))}</div></section>

      <section className="section" style={{ paddingTop: 10 }}><Reveal><div className="sec-head"><div><span className="eyebrow">Front page · {iss.date}</span><h2 style={{ fontSize: "clamp(34px,5vw,68px)" }}>The latest, <em>ranked.</em></h2></div><a href="/news">All news →</a></div></Reveal>
        <div className="front">
          {lead && <Reveal className="lead-story"><a href={`/story/${lead.id}`} className="lead-card"><span className="kind">{lead.category || lead.kind} {lead.city && `· ${lead.city}`}</span><h3>{clean(lead.title)}</h3><span className="mut">{lead.source_name} · {ago(lead.published_at)}</span></a></Reveal>}
          <div className="front-grid">{d.secondary.filter(a => !lead || a.id !== lead.id).slice(0, 6).map(a => <NewsCard key={a.id} a={a} />)}</div>
          <aside className="front-side">
            <div className="card"><h4>This week in numbers</h4>
              <dl className="nums"><div><dt>{c.stories7 ?? 0}</dt><dd>stories</dd></div><div><dt>{c.exp7 ?? 0}</dt><dd>centre events</dd></div><div><dt>{c.moves7 ?? 0}</dt><dd>leadership moves</dd></div></dl></div>
            <div className="card"><h4>Moves <a href="/people">all →</a></h4><ul className="mini">{moves.map(a => <li key={a.id}><a href={`/story/${a.id}`}>{clean(a.title)}</a></li>)}</ul></div>
            <div className="card"><h4>Deals <a href="/deals">all →</a></h4><ul className="mini">{deals.map(a => <li key={a.id}><a href={`/story/${a.id}`}>{clean(a.title)}</a></li>)}</ul></div>
          </aside></div></section>

      <section className="section"><Reveal><span className="eyebrow">Six months, one chart</span><h2 style={{ fontSize: "clamp(32px,4.6vw,60px)" }}>Coverage is <em>accelerating.</em></h2></Reveal>
        <Reveal><div className="bars">{d.months.map(m => (<div key={m.m} className="bar"><i style={{ "--h": `${Math.round((m.n / maxM) * 100)}%` }} /><b>{m.n}</b><span>{m.m}</span></div>))}</div>
          <p className="mut">Stories tracked per month, from public outlets. Method and sources on the <a href="/methodology">methodology page</a>.</p></Reveal></section>

      <Reveal><div className="finder-wrap"><h2 style={{ fontSize: "clamp(30px,4.5vw,56px)" }}>Three questions. <em>One shortlist.</em></h2>
        <Finder cities={[...new Set([...CITIES, ...dbCities])]} industries={inds} /></div></Reveal>

      <section className="section"><div className="refresh">
        <Reveal><div className="week"><div className="dial"><i /><i /><i /><i className="sweep" /><b><span>7<small>DAY CYCLE</small></span></b></div></div></Reveal>
        <Reveal delay={150}><span className="eyebrow">Paying should feel obvious</span><h2 style={{ fontSize: "clamp(34px,4.6vw,60px)" }}>You never wonder <em>if it&apos;s current.</em></h2>
          <ol className="steps"><li>News is collected every day</li><li>Jobs and company profiles are refreshed every week</li><li>The Weekly lands in your inbox on Monday</li><li>Every record shows its source and date</li></ol></Reveal></div></section>

      <section className="section" style={{ paddingTop: 0 }}><Reveal><span className="eyebrow">A look inside</span><h2 style={{ fontSize: "clamp(32px,4.6vw,60px)" }}>What the database <em>actually holds.</em></h2></Reveal>
        <Reveal><div className="peek tablewrap"><table><thead><tr><th>Company</th><th>Parent</th><th>Cities</th><th>Industry</th><th>Open jobs</th><th>Hiring contact</th></tr></thead>
          <tbody>{sample.map((r, i) => (<tr key={r.name}><td><b>{r.name}</b></td><td>{r.parent_company}</td><td>{(r.india_cities || []).join(", ")}</td><td>{r.industry}</td><td className="blur">{12 + i * 7}</td><td className="blur">name@company.com</td></tr>))}</tbody></table>
          <div className="peek-cta"><a className="btn" href="/signup">Create a free account <span>→</span></a><a className="btn ghost" href="/pricing">See what Pro adds</a></div></div></Reveal></section>

      <Reveal><section className="section" style={{ paddingTop: 0 }}><h2 style={{ fontSize: "clamp(32px,4.6vw,60px)" }}>The Weekly. <em>Every Monday.</em></h2>
        <p className="deck">One email: what opened, who moved, who raised, what changed in policy. <a href="/weekly">Read past issues</a>.</p>
        <ActionForm action={captureLead} submit="Send me the Weekly →" className="row"><input name="email" type="email" placeholder="you@company.com" required style={{ minWidth: 280 }} /></ActionForm></section></Reveal>
    </div></main>);
}
