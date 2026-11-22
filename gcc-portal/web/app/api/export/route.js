import { getUser, planOf } from "../../../lib/auth";
import { toCsv } from "../../../lib/csv";
import { q } from "../../../lib/db";
export async function GET(req) {
  const u = await getUser();
  if (!u) return new Response("Login required", { status: 401 });
  const p = planOf(u);
  if (!p.export) return new Response("Upgrade to export", { status: 403 });
  const sp = new URL(req.url).searchParams;
  const where = [], args = [];
  if (sp.get("q")) { args.push(`%${sp.get("q")}%`); where.push(`(name ILIKE $${args.length} OR parent_company ILIKE $${args.length})`); }
  if (sp.get("city")) { args.push(sp.get("city")); where.push(`$${args.length} = ANY(india_cities)`); }
  if (sp.get("industry")) { args.push(sp.get("industry")); where.push(`industry = $${args.length}`); }
  args.push(p.maxRows);
  const rows = await q(`SELECT name,domain,parent_company,hq_country,india_cities,industry,gcc_function,india_headcount_range,year_established,careers_url,last_refreshed_at
    FROM companies ${where.length ? "WHERE " + where.join(" AND ") : ""} ORDER BY last_refreshed_at DESC NULLS LAST LIMIT $${args.length}`, args);
  rows.forEach(r => { if (r.last_refreshed_at) r.last_refreshed_at = new Date(r.last_refreshed_at).toISOString(); });
  const csv = toCsv(rows, ["name", "domain", "parent_company", "hq_country", "india_cities", "industry", "gcc_function", "india_headcount_range", "year_established", "careers_url", "last_refreshed_at"]);
  return new Response(csv, { headers: { "content-type": "text/csv", "content-disposition": "attachment; filename=gcc-export.csv" } });
}
