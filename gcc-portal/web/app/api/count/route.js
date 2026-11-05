import { q } from "../../../lib/db";
export async function GET(req) {
  const sp = new URL(req.url).searchParams, where = [], args = [];
  if (sp.get("city")) { args.push(sp.get("city")); where.push(`$${args.length} = ANY(india_cities)`); }
  if (sp.get("industry")) { args.push(sp.get("industry")); where.push(`industry = $${args.length}`); }
  const [{ n }] = await q(`SELECT count(*)::int n FROM companies ${where.length ? "WHERE " + where.join(" AND ") : ""}`, args);
  return Response.json({ n });
}
