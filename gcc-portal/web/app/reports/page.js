import { q } from "../../lib/db";
export const dynamic = "force-dynamic";
export const metadata = { title: "GCC quarterly reports India – Q1, Q2, Q3, Q4", description: "Quarter-by-quarter GCC activity in India: new centres, expansions, hiring and headlines." };
export default async function Reports() {
  const [{ first }] = await q("SELECT least(coalesce(min(published_at),now()),coalesce((SELECT min(announced_at) FROM expansions),now())) first FROM articles");
  const now = new Date(), list = [];
  for (let y = now.getUTCFullYear(); y >= Math.max(2024, new Date(first).getUTCFullYear()); y--)
    for (let qn = 4; qn >= 1; qn--) { if (y === now.getUTCFullYear() && qn > Math.floor(now.getUTCMonth() / 3) + 1) continue;
      const s = new Date(Date.UTC(y, (qn - 1) * 3, 1)), e = new Date(Date.UTC(y, qn * 3, 1));
      const [c] = await q(`SELECT (SELECT count(*) FROM articles WHERE published_at>=$1 AND published_at<$2)::int news,(SELECT count(*) FROM expansions WHERE announced_at>=$1 AND announced_at<$2)::int exp`, [s, e]);
      list.push({ y, qn, ...c, live: y === now.getUTCFullYear() && qn === Math.floor(now.getUTCMonth() / 3) + 1 }); }
  return (<main className="wrap page"><span className="eyebrow"><i />Every quarter</span><h1>GCC India, <em>quarter by quarter.</em></h1>
    <div className="grid">{list.map(r => (<a key={`${r.y}${r.qn}`} className="card qcard" href={`/reports/${r.y}/q${r.qn}`}>
      <small className="mut">{r.live ? "LIVE · in progress" : "Report"}</small><h2 style={{ margin: "6px 0" }}>{r.y} · Q{r.qn}</h2>
      <span>{r.news} stories · {r.exp} expansions</span></a>))}</div></main>);
}
