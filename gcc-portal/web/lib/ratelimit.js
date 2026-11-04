// DB-backed fixed-window rate limiter (table rate_limits, see db/schema.sql). Works across
// several web instances and restarts. Fails open if the table is unreachable (logged), so a DB hiccup
// never locks everyone out of login.
import crypto from "crypto";
import { headers } from "next/headers";
import { q } from "./db";

export function clientIp() {
  try {
    const h = headers();
    // Behind Caddy/nginx/Vercel the first X-Forwarded-For entry is the client. Direct exposure without a proxy
    // lets a caller spoof it, which is why login also has a per-email bucket that ignores the IP.
    const xff = (h.get("x-forwarded-for") || "").split(",")[0].trim();
    return xff || h.get("x-real-ip") || "unknown";
  } catch { return "unknown"; }
}
const tag = (s) => crypto.createHash("sha256").update(String(s).toLowerCase()).digest("hex").slice(0, 24);

// Count one attempt in `bucket` for `id`. Returns { ok, count, retryAfter } (retryAfter in seconds).
export async function hit(bucket, id, max, windowSec) {
  const key = `${bucket}:${tag(id)}`;
  try {
    const [r] = await q(
      `INSERT INTO rate_limits(key,count,window_start) VALUES($1,1,now())
       ON CONFLICT (key) DO UPDATE SET
         count = CASE WHEN rate_limits.window_start < now() - ($2::int * interval '1 second') THEN 1 ELSE rate_limits.count + 1 END,
         window_start = CASE WHEN rate_limits.window_start < now() - ($2::int * interval '1 second') THEN now() ELSE rate_limits.window_start END
       RETURNING count, GREATEST(1, ceil(extract(epoch FROM (window_start + ($2::int * interval '1 second') - now()))))::int AS retry`,
      [key, windowSec]);
    if (Math.random() < 0.01) q("DELETE FROM rate_limits WHERE window_start < now() - interval '1 day'").catch(() => {});
    return { ok: r.count <= max, count: r.count, retryAfter: r.retry };
  } catch (e) { console.error("ratelimit: failing open:", e.message); return { ok: true, count: 0, retryAfter: 0 }; }
}
export async function reset(bucket, id) { try { await q("DELETE FROM rate_limits WHERE key=$1", [`${bucket}:${tag(id)}`]); } catch {} }

export const tooMany = (r) => ({ error: `Too many attempts. Try again in ${Math.max(1, Math.ceil(r.retryAfter / 60))} minute(s).` });

// Login/signup guard: max 10 attempts per 15 minutes for one IP+email, plus 30 per 15 minutes per email from anywhere.
export async function authGuard(kind, email) {
  const ip = clientIp();
  const a = await hit(kind, `${ip}|${email}`, 10, 900);
  if (!a.ok) return a;
  const b = await hit(`${kind}-email`, email, 30, 900);
  return b;
}
export const authGuardReset = (kind, email) => reset(kind, `${clientIp()}|${email}`);
