import { notFound } from "next/navigation";
import { q } from "../../../lib/db";
import { getUser, planOf } from "../../../lib/auth";
import { clean } from "../../../lib/content";
import { toggleSave } from "../../actions";
import CompanyHeader from "../../../components/CompanyHeader";
import FollowButton from "../../../components/FollowButton";
import Comments from "../../../components/Comments";
import "./profile.css";
export const dynamic = "force-dynamic";

const ymd = (x) => (x ? new Date(x).toISOString().slice(0, 10) : "");
const num = (n) => (n == null || n === "" ? null : Number(n).toLocaleString("en-IN"));
const load = async (id) => (Number.isInteger(id) && id > 0 && id < 2 ** 31 ? (await q("SELECT * FROM companies WHERE id=$1", [id]))[0] : null);

export async function generateMetadata({ params }) {
  const c = await load(Number(params.id));
  if (!c) return { title: "Company not found" };
  const desc = c.description || `${c.name}: ${[c.parent_company && `parent ${c.parent_company}`, (c.india_cities || []).join(", "), c.industry].filter(Boolean).join(" · ")}. News, expansions, people moves and open India jobs.`;
  return { title: `${c.name} GCC in India`, description: desc.slice(0, 200), alternates: { canonical: `/companies/${c.id}` } };
}

function Fact({ k, v, sub }) {
  return (<div className="co-fact"><dt>{k}</dt><dd className={v == null ? "nil" : ""}>{v ?? "—"}{sub && <small>{sub}</small>}</dd></div>);
}

export default async function Company({ params }) {
  const id = Number(params.id) || 0;
  const u = await getUser(); const p = planOf(u);
  const c = await load(id);
  if (!c) notFound();
  const names = [...new Set([c.name, c.parent_company, (c.parent_company || "").replace(/\s*\(.*?\)\s*/g, ""), ...(c.aliases || [])].filter(Boolean).map(s => s.toLowerCase()))];
  const lim = p.signals;
  const [news, jobs, exps, moves, funds, sib, [sv], [cnt]] = await Promise.all([
    q("SELECT id,title,source_name,published_at,category,city FROM articles WHERE company_id=$1 AND coalesce(relevant,true) ORDER BY published_at DESC NULLS LAST, id DESC LIMIT $2", [id, lim]),
    q("SELECT * FROM job_postings WHERE company_id=$1 ORDER BY first_seen DESC LIMIT $2", [id, p.jobs]),
    q("SELECT id,city,event,summary,company_name,source_url,announced_at FROM expansions WHERE company_id=$1 ORDER BY announced_at DESC NULLS LAST LIMIT $2", [id, lim]),
    q("SELECT id,person,role,city,kind,source_url,published_at FROM people_moves WHERE company_id=$1 ORDER BY published_at DESC NULLS LAST LIMIT $2", [id, lim]),
    q("SELECT id,company_name,kind,amount_text,round,investors,summary,source_url,published_at FROM fundings WHERE lower(company_name)=ANY($1) ORDER BY published_at DESC NULLS LAST LIMIT $2", [names, lim]),
    q("SELECT id,name,india_cities FROM companies WHERE parent_company=$1 AND id<>$2 ORDER BY name LIMIT 8", [c.parent_company || "\u0000", id]),
    u ? q("SELECT 1 FROM saved_companies WHERE user_id=$1 AND company_id=$2", [u.id, id]) : [null],
    q(`SELECT (SELECT count(*)::int FROM job_postings WHERE company_id=$1) nj,
              (SELECT count(*)::int FROM articles WHERE company_id=$1 AND coalesce(relevant,true)) nn,
              (SELECT count(*)::int FROM expansions WHERE company_id=$1) ne,
              (SELECT count(*)::int FROM people_moves WHERE company_id=$1) nm,
              (SELECT count(*)::int FROM fundings WHERE lower(company_name)=ANY($2)) nf`, [id, names])]);
  const { nj, nn, ne, nm, nf } = cnt;
  const clipped = nj > jobs.length || nn > news.length || ne > exps.length || nm > moves.length || nf > funds.length;
  const cities = c.india_cities || [];
  const ld = { "@context": "https://schema.org", "@type": "Organization", name: c.parent_company || c.name, url: c.website || undefined,
    description: c.description || undefined, foundingDate: c.founded_year ? String(c.founded_year) : undefined,
    numberOfEmployees: c.global_employees ? { "@type": "QuantitativeValue", value: Number(c.global_employees) } : undefined,
    tickerSymbol: c.ticker || undefined, sameAs: [c.wikipedia_url, c.wikidata_id && `https://www.wikidata.org/wiki/${c.wikidata_id}`].filter(Boolean) };

  const actions = (<>
    {u && <form action={toggleSave.bind(null, id)}><button className="btn ghost">{sv ? "★ Saved" : "☆ Save"}</button></form>}
    <FollowButton kind="company" value={id} label={c.parent_company || c.name} />
  </>);

  return (<main className="wrap page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld).replace(/</g, "\\u003c") }} />
    <p><a className="co-back" href="/companies">← All companies</a></p>
    <CompanyHeader c={c} actions={actions} />

    <dl className="co-facts" aria-label="Key facts">
      {[
        ["India headcount", c.india_headcount_range], ["Global employees", num(c.global_employees), c.global_employees ? "parent company, Wikidata" : null],
        ["GCC function", c.gcc_function], ["GCC set up in India", c.year_established], ["Parent founded", c.founded_year],
        ["Cities in India", cities.length ? String(cities.length) : null, cities.slice(0, 3).join(", ") || null],
        ["Open India jobs", String(nj), nj ? "from public job boards" : "none seen in last refresh"],
        ["Stories linked", String(nn), [ne && `${ne} expansion${ne > 1 ? "s" : ""}`, nm && `${nm} move${nm > 1 ? "s" : ""}`, nf && `${nf} deal${nf > 1 ? "s" : ""}`].filter(Boolean).join(" · ") || null],
      ].filter(f => f[1] != null && f[1] !== "").map(([k, v, sub]) => <Fact key={k} k={k} v={String(v)} sub={sub} />)}
    </dl>
    {c.tech_stack?.length > 0 && <p className="co-stack" aria-label="Tech stack">{c.tech_stack.map(t => <span key={t} className="tag">{t}</span>)}</p>}

    <div className="co-cols">
      <section>
        <h2>Latest news <span className="co-n">{nn}</span></h2>
        {news.length > 0 ? <ul className="co-list">{news.map(a => (
          <li key={a.id}><span className="co-when">{ymd(a.published_at)}</span>
            <div><a className="t" href={`/story/${a.id}`}>{clean(a.title)}</a>
              <div className="sub"><span>{a.source_name}</span>{a.city && <span>{a.city}</span>}{a.category && a.category !== "other" && <span className="ev">{a.category}</span>}</div></div></li>))}</ul>
          : <p className="co-empty">No stories linked to {c.parent_company || c.name} yet. We match headlines on the company name and its known aliases; new matches appear after each news run.</p>}

        <h2>India jobs <span className="co-n">{nj}</span></h2>
        {jobs.length > 0 ? <ul className="co-list">{jobs.map(j => (
          <li key={j.id}><span className="co-when">{ymd(j.first_seen)}</span>
            <div><a className="t" href={j.url} target="_blank" rel="nofollow noopener">{j.title}</a>
              <div className="sub">{j.location && <span>{j.location}</span>}{j.department && <span>{j.department}</span>}</div></div></li>))}</ul>
          : <p className="co-empty">No open India roles found on the public job boards we read.{c.careers_url && <> Try the <a href={c.careers_url} target="_blank" rel="nofollow noopener">careers page</a>.</>}</p>}
      </section>

      <aside>
        <h2>Expansions <span className="co-n">{ne}</span></h2>
        {exps.length > 0 ? <ul className="co-list">{exps.map(e => (
          <li key={e.id}><span className="co-when">{ymd(e.announced_at)}</span>
            <div><a className="t" href={e.source_url} target="_blank" rel="nofollow noopener">{clean(e.summary || e.company_name)}</a>
              <div className="sub"><span className={`ev ${e.event}`}>{e.event}</span>{e.city && <span>{e.city}</span>}</div></div></li>))}</ul>
          : <p className="co-empty">No launches or expansions tracked.</p>}

        <h2>People moves <span className="co-n">{nm}</span></h2>
        {moves.length > 0 ? <ul className="co-list">{moves.map(m => (
          <li key={m.id}><span className="co-when">{ymd(m.published_at)}</span>
            <div><a className="t" href={m.source_url} target="_blank" rel="nofollow noopener">{m.person}</a>
              <div className="sub"><span>{m.role}</span>{m.city && <span>{m.city}</span>}<span className="ev">{m.kind}</span></div></div></li>))}</ul>
          : <p className="co-empty">No leadership changes tracked.</p>}

        {(funds.length > 0 || nf > 0) && <>
          <h2>Funding &amp; deals <span className="co-n">{nf}</span></h2>
          <ul className="co-list">{funds.map(f => (
            <li key={f.id}><span className="co-when">{ymd(f.published_at)}</span>
              <div><a className="t" href={f.source_url} target="_blank" rel="nofollow noopener">{clean(f.summary || f.company_name)}</a>
                <div className="sub">{f.amount_text && <span>{f.amount_text}</span>}{f.round && <span className="ev">{f.round}</span>}{f.investors && <span>{f.investors}</span>}</div></div></li>))}</ul></>}

        {sib.length > 0 && <>
          <h2>Same parent</h2>
          <ul className="co-mini">{sib.map(s => <li key={s.id}><b><a href={`/companies/${s.id}`}>{s.name}</a></b><span>{(s.india_cities || []).join(", ")}</span></li>)}</ul></>}
      </aside>
    </div>

    {clipped && <p className="co-lock"><b>{p.label} plan:</b> this view is capped at {p.signals} items per news, expansion and people list and {p.jobs} jobs. <a href="/pricing">Upgrade for the full history</a>.</p>}

    <section className="co-src" aria-labelledby="src-h">
      <h2 id="src-h">Data sources &amp; last refreshed</h2>
      <dl>
        <dt>Company record</dt><dd>{c.source === "seed" ? "Curated seed list" : "Public research"} of GCCs in India. Cities, headcount range and function are estimates; see <a href="/methodology">methodology</a>.</dd>
        <dt>Profile facts</dt><dd>{c.wikidata_id
          ? <>Parent company matched on <a href={`https://www.wikidata.org/wiki/${c.wikidata_id}`} target="_blank" rel="nofollow noopener">Wikidata {c.wikidata_id}</a> by official website{c.wikipedia_url && <>; summary text from <a href={c.wikipedia_url} target="_blank" rel="nofollow noopener">Wikipedia</a> (CC BY-SA 4.0)</>}. Employees, founding year, ticker and logo come from the same record.</>
          : <>No confident Wikidata match for {c.parent_company || c.name}, so description, employees, founding year and logo are left blank instead of guessed.</>}</dd>
        <dt>News</dt><dd>Headlines and links from Google News and publisher feeds. We store the headline, outlet, date and link only; the story stays with the publisher.</dd>
        <dt>Jobs</dt><dd>Public applicant-tracking boards{c.careers_url ? <> and the <a href={c.careers_url} target="_blank" rel="nofollow noopener">company careers page</a></> : ""}.</dd>
        <dt>Last refreshed</dt><dd>{ymd(c.last_refreshed_at) || "pending first refresh"}</dd>
      </dl>
    </section>

    <section className="co-comm"><Comments targetType="company" targetId={id} next={`/companies/${id}`} /></section>
  </main>);
}
