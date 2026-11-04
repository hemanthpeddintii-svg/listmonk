import { q } from "../lib/db";
export const dynamic = "force-dynamic";
export default async function sitemap() {
  const base = process.env.SITE_URL || "http://localhost:3000";
  const rows = await q("SELECT id,last_refreshed_at FROM companies").catch(() => []);
  const stories = await q("SELECT id,published_at FROM articles ORDER BY published_at DESC NULLS LAST LIMIT 5000").catch(() => []);
  const cities = ["Bengaluru","Hyderabad","Pune","Chennai","Mumbai","Delhi NCR","Gurugram","Noida","Kolkata","Ahmedabad","Coimbatore","Kochi"];
  return [{ url: base }, ...["pricing","companies","news","expansions","people","deals","policies","events","reports","jobs","cities","learn","weekly","methodology","search"].map(x => ({ url: `${base}/${x}` })), ...cities.map(c => ({ url: `${base}/cities/${encodeURIComponent(c)}` })),
    ...stories.map(r => ({ url: `${base}/story/${r.id}`, lastModified: r.published_at ?? undefined })), ...rows.map(r => ({ url: `${base}/companies/${r.id}`, lastModified: r.last_refreshed_at ?? undefined }))];
}
