import { q } from "../../lib/db";
export const dynamic = "force-dynamic";
export const metadata = { title: "Methodology: how GCC Intel gathers and checks data" };
export default async function Methodology() {
  const [c] = await q(`SELECT (SELECT count(*) FROM companies)::int companies,(SELECT count(*) FROM articles)::int articles,(SELECT count(DISTINCT source_name) FROM articles)::int outlets,
    (SELECT count(*) FROM job_postings)::int jobs,(SELECT max(published_at) FROM articles) latest,(SELECT max(last_refreshed_at) FROM companies) refreshed`).catch(() => [{}]);
  return (<main className="wrap page prose"><span className="eyebrow"><i />Trust</span><h1>How we know <em>what we know.</em></h1>
    <p>If you are paying for this, you should be able to check it. Here is exactly what we do and where it is weak.</p>
    <div className="facts" style={{ margin: "20px 0" }}>
      <div className="card"><b className="big">{c.companies}</b><br />companies</div><div className="card"><b className="big">{c.articles}</b><br />stories from {c.outlets} outlets</div><div className="card"><b className="big">{c.jobs}</b><br />job postings</div></div>
    <h2>Sources</h2><ul><li><b>News:</b> public RSS feeds and news search. We store the headline, outlet, link and date, never the article text. Every story links to its publisher.</li>
      <li><b>Companies:</b> multinational parents with India centres, compiled from public information and press reports. Profiles are enriched from Wikidata and Wikipedia where a confident match exists.</li>
      <li><b>Jobs:</b> public job-board APIs of the companies that publish them. Banks and others on closed systems are under-represented.</li>
      <li><b>Policies and events:</b> official or reputable pages we read, each with its source link.</li></ul>
    <h2>Freshness</h2><ul><li>News: collected daily.</li><li>Jobs and company profiles: refreshed weekly.</li><li>The Weekly digest: every Monday.</li></ul>
    <p className="mut">Latest story in database: {c.latest ? new Date(c.latest).toISOString().slice(0, 16).replace("T", " ") + " UTC" : "n/a"}.</p>
    <h2>Known limits</h2><ul><li>Expansion and people-move entries are detected automatically from headlines and marked unverified until a human confirms them.</li><li>We do not publish headcounts we cannot source. If a field is blank, we do not know.</li><li>Coverage of smaller or quieter centres is thinner than for well-covered ones.</li></ul>
    <h2>Corrections</h2><p>Spotted an error? Comment on the story or email the address on the Weekly. We fix and date every correction.</p></main>);
}
