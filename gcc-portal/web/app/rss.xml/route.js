import { q } from "../../lib/db";
import { siteUrl, xml, cdata, rfc822, cleanTitle, storyLink, xmlResponse } from "../../lib/rss";
export const dynamic = "force-dynamic";
export async function GET() {
  const base = siteUrl();
  const rows = await q(`SELECT id,slug,title,summary,body,source_name,source_url,city,category,kind,published_at
                        FROM articles ORDER BY published_at DESC NULLS LAST, id DESC LIMIT 50`).catch(() => []);
  const items = rows.map(a => {
    const link = storyLink(a);
    const desc = a.summary || [a.source_name, a.city].filter(Boolean).join(" · ") || "GCC news";
    return `<item><title>${xml(cleanTitle(a.title))}</title><link>${xml(link)}</link><guid isPermaLink="false">gcc-intel-article-${a.id}</guid>` +
      (a.published_at ? `<pubDate>${rfc822(a.published_at)}</pubDate>` : "") +
      `<description>${xml(desc.slice(0, 300))}</description>` +
      [a.category, a.city, a.kind].filter(Boolean).map(c => `<category>${xml(c)}</category>`).join("") + `</item>`;
  }).join("");
  const last = rows.find(r => r.published_at)?.published_at;
  return xmlResponse(`<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>GCC Intel India: latest stories</title><link>${xml(base)}/news</link>
<atom:link href="${xml(base)}/rss.xml" rel="self" type="application/rss+xml"/>
<description>Headlines on Global Capability Centers in India: new centres, expansions, leadership moves, deals and policy.</description>
<language>en-in</language>${last ? `<lastBuildDate>${rfc822(last)}</lastBuildDate>` : ""}<ttl>60</ttl>
${items}
</channel></rss>`);
}
