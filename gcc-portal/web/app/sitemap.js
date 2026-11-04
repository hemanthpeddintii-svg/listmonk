import { q } from "../lib/db";
export const dynamic = "force-dynamic";
export default async function sitemap() {
  const base = process.env.SITE_URL || "http://localhost:3000";
  const rows = await q("SELECT id,last_refreshed_at FROM companies").catch(() => []);
  const cities = ["Bengaluru","Hyderabad","Pune","Chennai","Mumbai","Delhi NCR","Gurugram","Noida","Kolkata","Ahmedabad","Coimbatore","Kochi"];
  return [{ url: base }, ...["pricing","companies","news","expansions","reports","jobs","cities","learn"].map(x => ({ url: `${base}/${x}` })), ...cities.map(c => ({ url: `${base}/cities/${encodeURIComponent(c)}` })),
    ...rows.map(r => ({ url: `${base}/companies/${r.id}`, lastModified: r.last_refreshed_at ?? undefined }))];
}
