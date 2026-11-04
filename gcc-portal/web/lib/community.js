import { q } from "./db";

export const TOPICS = ["funding", "leadership", "expansion", "hiring", "policy", "ai", "other"];
export const TARGETS = ["article", "company", "expansion"];

// "Top this week" for /news: highest score first, then most-discussed, then newest.
// Only stories that were published inside the window; falls back to newest-first when nobody has voted yet.
export const getTopStories = (days = 7, limit = 24) =>
  q(`SELECT * FROM articles
      WHERE published_at > now() - ($1::int || ' days')::interval
      ORDER BY score DESC, comment_count DESC, published_at DESC NULLS LAST
      LIMIT $2`, [Math.max(1, Number(days) || 7), Math.max(1, Math.min(100, Number(limit) || 24))]);

// Public display name: the person's name, else the part of their email before the @. Never the full address.
export const displayName = (u) => {
  const n = String(u?.name || "").trim();
  if (n && !n.includes("@")) return n.slice(0, 60);
  return String(u?.email || n || "member").split("@")[0].slice(0, 40) || "member";
};

export async function getFollows(userId) {
  const rows = await q("SELECT kind,value FROM follows WHERE user_id=$1 ORDER BY created_at DESC", [userId]);
  const by = (k) => rows.filter(r => r.kind === k).map(r => r.value);
  return { company: by("company"), city: by("city"), topic: by("topic"), total: rows.length };
}

// Newest-first stories from followed companies (articles.company_id), cities and topics (articles.category).
export async function getFeed(userId, limit = 30) {
  return q(`SELECT a.*, c.name AS company_name FROM articles a LEFT JOIN companies c ON c.id=a.company_id
    WHERE a.company_id IN (SELECT value::int FROM follows WHERE user_id=$1 AND kind='company' AND value ~ '^[0-9]+$')
       OR a.city IN (SELECT value FROM follows WHERE user_id=$1 AND kind='city')
       OR a.category IN (SELECT value FROM follows WHERE user_id=$1 AND kind='topic')
    ORDER BY a.published_at DESC NULLS LAST LIMIT $2`, [userId, Math.max(1, Math.min(100, limit))]);
}
export async function getFeedCount(userId, days = 7) {
  const [r] = await q(`SELECT count(*)::int n FROM articles a
    WHERE a.published_at > now() - ($2::int || ' days')::interval AND (
       a.company_id IN (SELECT value::int FROM follows WHERE user_id=$1 AND kind='company' AND value ~ '^[0-9]+$')
       OR a.city IN (SELECT value FROM follows WHERE user_id=$1 AND kind='city')
       OR a.category IN (SELECT value FROM follows WHERE user_id=$1 AND kind='topic'))`, [userId, days]);
  return r.n;
}
export async function followerCount(kind, value) {
  const [r] = await q("SELECT count(*)::int n FROM follows WHERE kind=$1 AND value=$2", [kind, String(value)]);
  return r.n;
}
