// Server-side helpers for the admin screen. Never import from a client component.
import { q } from "./db";

export const TOPICS = [["expansions", "New and expanded centres"], ["leadership", "Leadership moves"], ["funding", "Funding and deals"], ["policy", "Policy"], ["hiring", "Who is hiring"], ["ai", "AI in the centres"]];

// { total, confirmed, pending, unsubscribed, last7d }
export async function countSubscribers() {
  const [r] = await q(`SELECT count(*)::int total,
      count(*) FILTER (WHERE confirmed AND unsubscribed_at IS NULL)::int confirmed,
      count(*) FILTER (WHERE NOT confirmed AND unsubscribed_at IS NULL)::int pending,
      count(*) FILTER (WHERE unsubscribed_at IS NOT NULL)::int unsubscribed,
      count(*) FILTER (WHERE created_at > now() - interval '7 days')::int last7d
    FROM subscribers`);
  return r;
}

// status: "all" | "confirmed" | "pending" | "unsubscribed". Tokens are never returned.
export async function listSubscribers({ status = "all", limit = 50, offset = 0 } = {}) {
  const w = { all: "TRUE", confirmed: "confirmed AND unsubscribed_at IS NULL", pending: "NOT confirmed AND unsubscribed_at IS NULL", unsubscribed: "unsubscribed_at IS NOT NULL" }[status] || "TRUE";
  return q(`SELECT id,email,topics,cities,confirmed,confirmed_at,created_at,unsubscribed_at,last_digest,source
            FROM subscribers WHERE ${w} ORDER BY created_at DESC LIMIT $1 OFFSET $2`, [Math.min(500, Number(limit) || 50), Number(offset) || 0]);
}
