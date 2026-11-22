import { notFound } from "next/navigation";
import { q } from "../../../lib/db";
export const dynamic = "force-dynamic";
export async function generateMetadata({ params }) { const [a] = await q("SELECT title,summary FROM articles WHERE slug=$1", [params.slug]); return a ? { title: a.title, description: a.summary } : {}; }
export default async function Article({ params }) {
  const [a] = await q("SELECT * FROM articles WHERE slug=$1 AND body IS NOT NULL", [params.slug]); if (!a) notFound();
  return (<main className="wrap page prose"><p><a href="/news">← News</a></p><span className="eyebrow">{a.kind}{a.city && ` · ${a.city}`}</span><h1>{a.title}</h1>
    <p className="mut">{new Date(a.published_at).toISOString().slice(0, 10)}</p>
    {a.body.split(/\n\n+/).map((p, i) => <p key={i}>{p}</p>)}</main>);
}
