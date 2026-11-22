import { q } from "../../../lib/db";
import { siteUrl, xml, cdata, rfc822, xmlResponse, bodyOf } from "../../../lib/rss";
export const dynamic = "force-dynamic";
export async function GET() {
  const base = siteUrl();
  const rows = await q(`SELECT week_start::text ws, title, html, stats FROM digests ORDER BY week_start DESC LIMIT 26`).catch(() => []);
  const now = Date.now();
  const items = rows.map(d => {
    const published = Math.min(now, Date.parse(d.ws + "T00:00:00Z") + 7 * 864e5 + 1.5 * 36e5);   // Monday 07:00 IST
    const hl = d.stats?.headline?.title, n = d.stats?.numbers || {};
    const desc = `${hl ? hl + ". " : ""}${n.stories ?? 0} stories, ${n.new_centres ?? 0} new centres, ${n.expanded ?? 0} expansions.`;
    return `<item><title>${xml(d.title)}</title><link>${base}/weekly/${d.ws}</link><guid isPermaLink="true">${base}/weekly/${d.ws}</guid><pubDate>${rfc822(published)}</pubDate>` +
      `<description>${xml(desc)}</description><content:encoded>${cdata(bodyOf(d.html, base))}</content:encoded></item>`;
  }).join("");
  return xmlResponse(`<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<title>The GCC Weekly</title><link>${base}/weekly</link>
<atom:link href="${base}/weekly/rss.xml" rel="self" type="application/rss+xml"/>
<description>One issue every Monday: new and expanded GCCs in India, leadership moves, deals, policy and hiring, built from the GCC Intel database.</description>
<language>en-in</language>${rows[0] ? `<lastBuildDate>${rfc822(Math.min(now, Date.parse(rows[0].ws + "T00:00:00Z") + 7 * 864e5))}</lastBuildDate>` : ""}<ttl>360</ttl>
${items}
</channel></rss>`, 900);
}
