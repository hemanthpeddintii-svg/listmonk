import { q } from "../lib/db";
import { ActionForm } from "../components/Forms";
import IndiaMap from "../components/IndiaMap";
import Finder from "../components/Finder";
import NewsCard from "../components/NewsCard";
import { clean, ago } from "../lib/content";
import Reveal from "../components/Reveal";
import CountUp from "../components/CountUp";
import { captureLead } from "./actions";
export const dynamic = "force-dynamic";
const CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi NCR", "Mumbai"];
export default async function Home() {
  const [s] = await q(`SELECT (SELECT count(*) FROM companies)::int companies,(SELECT count(*) FROM job_postings)::int jobs,
    (SELECT count(*) FROM signals)::int signals`).catch(() => [{ companies: 0, jobs: 0, signals: 0 }]);
  const dbCities = (await q("SELECT DISTINCT unnest(india_cities) c FROM companies ORDER BY 1").catch(() => [])).map(r => r.c);
  const inds = (await q("SELECT industry i,count(*) n FROM companies WHERE industry IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").catch(() => [])).map(r => r.i);
  const names = (await q("SELECT name FROM companies ORDER BY last_refreshed_at DESC NULLS LAST LIMIT 20").catch(() => [])).map(r => r.name);
  const ticker = names.length ? names : ["Microsoft", "Goldman Sachs", "Walmart", "JPMorgan", "Airbus", "Siemens", "Target", "Cisco"];
  const news = await q("SELECT * FROM articles ORDER BY published_at DESC NULLS LAST LIMIT 7").catch(() => []);
  const exps = await q("SELECT * FROM expansions ORDER BY announced_at DESC LIMIT 6").catch(() => []);
  const now = new Date(), cq = Math.floor(now.getUTCMonth() / 3) + 1, cy = now.getUTCFullYear();
  const cities = [...new Set([...CITIES, ...dbCities])];
  return (<main>
    <section className="hero"><IndiaMap />
      <div className="wrap" style={{ width: "100%" }}><div className="hero-copy">
        <div className="eyebrow"><i />Live · refreshed every 72 hours</div>
        <h1><span className="line"><span>Every GCC</span></span><span className="line"><span>in India,</span></span><span className="line"><span><em>alive</em> on one map.</span></span></h1>
        <p className="lead">2,000+ Global Capability Centers — who runs them, where they sit, what they&apos;re hiring for this week.</p>
        <div className="cta"><a className="btn" href="#finder">Find your GCCs <span>↓</span></a><a className="btn ghost" href="/companies">Browse all</a></div>
      </div></div><div className="scrollhint">SCROLL ↓</div></section>

    <div className="ticker-clip"><div className="ticker"><div className="ticker-track">{[...ticker, ...ticker].map((n, i) => <span key={i}>{n} <b>✦</b> </span>)}</div></div></div>

    <div className="wrap">
      <section className="section"><Reveal><h2>The market moves weekly. <em>Your list should too.</em></h2></Reveal>
        <div className="stats">
          <Reveal className="block c1" delay={0}><b><CountUp to={Math.max(s.companies, 0)} /></b><span>companies tracked</span></Reveal>
          <Reveal className="block c2" delay={100}><b><CountUp to={s.jobs} /></b><span>India job postings</span></Reveal>
          <Reveal className="block c3" delay={200}><b><CountUp to={s.signals} /></b><span>news &amp; expansion signals</span></Reveal>
          <Reveal className="block c4" delay={300}><b><CountUp to={3} suffix="d" /></b><span>refresh cycle</span></Reveal></div></section>


      <section className="section"><Reveal><div className="sec-head"><h2>Latest from the <em>GCC world</em></h2><a href="/news">All news →</a></div></Reveal>
        <div className="ngrid">{news.map((a, i) => <NewsCard key={a.id} a={a} big={i === 0} />)}</div></section>

      <section className="section" style={{ paddingTop: 0 }}><div className="split">
        <Reveal><div className="sec-head"><h2 style={{ fontSize: "clamp(30px,4vw,52px)" }}>Opening, expanding, <em>closing.</em></h2><a href="/expansions">Tracker →</a></div>
          <ul className="timeline">{exps.map(r => <li key={r.id}><span className={"ev " + r.event}>{r.event}</span><div><a href={r.source_url} target="_blank" rel="nofollow noopener"><b>{clean(r.summary || r.company_name)}</b></a><div className="mut">{r.city} {ago(r.announced_at)}</div></div></li>)}</ul></Reveal>
        <Reveal delay={120}><div className="sec-head"><h2 style={{ fontSize: "clamp(30px,4vw,52px)" }}>Every quarter, <em>a report.</em></h2><a href="/reports">All reports →</a></div>
          <div className="qgrid">{[0, 1, 2, 3].map(i => { let y = cy, qn = cq - i; while (qn < 1) { qn += 4; y--; } return <a key={i} className="card qcard" href={`/reports/${y}/q${qn}`}><small className="mut">{i === 0 ? "LIVE" : "REPORT"}</small><h2 style={{ margin: "4px 0 0" }}>Q{qn} {y}</h2></a>; })}</div>
          <p className="mut" style={{ marginTop: 18 }}>Searching &ldquo;GCC&rdquo;? It can also mean the Gulf Cooperation Council. <a href="/learn">Here&apos;s the difference →</a></p></Reveal></div></section>

      <Reveal><div className="finder-wrap"><h2 style={{ fontSize: "clamp(30px,4.5vw,56px)" }}>Three questions. <em>One shortlist.</em></h2>
        <Finder cities={cities} industries={inds} /></div></Reveal>

      <section className="section"><div className="refresh">
        <Reveal><div className="dial"><i /><i /><i /><i className="sweep" /><b><span>72<small>HOURS</small></span></b></div></Reveal>
        <Reveal delay={150}><h2 style={{ fontSize: "clamp(34px,4.6vw,60px)" }}>A database that <em>never sits still.</em></h2>
          <ol className="steps"><li>Crawl careers pages &amp; job boards</li><li>Detect hiring surges and expansions</li><li>Read the news around each parent</li><li>Publish — newest first</li></ol></Reveal></div></section>

      <Reveal><section className="section" style={{ paddingTop: 0 }}><h2 style={{ fontSize: "clamp(32px,4.6vw,60px)" }}>Get the GCC market brief — <em>free.</em></h2>
        <ActionForm action={captureLead} submit="Email me →" className="row"><input name="email" type="email" placeholder="you@company.com" required style={{ minWidth: 280 }} /></ActionForm></section></Reveal>
    </div></main>);
}
