import fs from "fs";
import path from "path";

export const siteUrl = () => (process.env.SITE_URL || "http://localhost:3000").replace(/\/$/, "");
export const xml = (s = "") => String(s).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
export const cdata = (s = "") => `<![CDATA[${String(s).replace(/\]\]>/g, "]]]]><![CDATA[>")}]]>`;
export const rfc822 = (d) => new Date(d).toUTCString();
export const cleanTitle = (t = "") => t.replace(/\s+-\s+[^-]+$/, "");

// Does the app have a /story/[id] route? Env STORY_PAGES=1|0 forces it; otherwise look for the built route.
let storyCache;
export function hasStoryRoute() {
  if (process.env.STORY_PAGES === "1") return true;
  if (process.env.STORY_PAGES === "0") return false;
  if (storyCache === undefined) {
    const dist = process.env.NEXT_DIST || ".next";
    storyCache = ["app/story", "src/app/story"].some(p => fs.existsSync(path.join(process.cwd(), p))) ||
      fs.existsSync(path.join(process.cwd(), dist, "server", "app", "story"));
  }
  return storyCache;
}
export function storyLink(a) {
  const base = siteUrl();
  if (a.body && a.slug) return `${base}/news/${a.slug}`;
  if (hasStoryRoute()) return `${base}/story/${a.id}`;
  return a.source_url || `${base}/news`;
}
export const xmlResponse = (body, maxAge = 600) => new Response(body, { headers: { "Content-Type": "application/rss+xml; charset=utf-8", "Cache-Control": `public, max-age=${maxAge}, s-maxage=${maxAge}` } });

// Digest HTML document -> body markup. base="" keeps links relative (web), otherwise absolute (feeds).
export const bodyOf = (html, base = "") => ((/<body[^>]*>([\s\S]*)<\/body>/i.exec(html) || [0, html])[1])
  .replace(/<!--legal-start-->[\s\S]*?<!--legal-end-->/g, "").replace(/\{\{SITE\}\}/g, base);
