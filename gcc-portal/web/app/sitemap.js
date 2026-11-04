import { q } from "../lib/db";
export const dynamic = "force-dynamic";
export default async function sitemap() {
  const base = process.env.SITE_URL || "http://localhost:3000";
  const rows = await q("SELECT id,last_refreshed_at FROM companies").catch(() => []);
  return [{ url: base }, { url: base + "/pricing" }, { url: base + "/companies" },
    ...rows.map(r => ({ url: `${base}/companies/${r.id}`, lastModified: r.last_refreshed_at ?? undefined }))];
}
