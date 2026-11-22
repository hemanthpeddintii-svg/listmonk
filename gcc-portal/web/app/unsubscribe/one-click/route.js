// RFC 8058 one-click unsubscribe: mail clients POST here (List-Unsubscribe-Post header). GET falls back to the page.
import { q } from "../../../lib/db";
import { clientIp, hit } from "../../../lib/ratelimit";
export const dynamic = "force-dynamic";
const ok = (t) => /^[a-f0-9]{16,128}$/.test(t);
export async function POST(req) {
  const token = new URL(req.url).searchParams.get("token") || "";
  if (!ok(token)) return new Response("bad token", { status: 400 });
  if (!(await hit("unsub", clientIp(), 60, 600)).ok) return new Response("slow down", { status: 429 });
  await q("UPDATE subscribers SET unsubscribed_at=COALESCE(unsubscribed_at,now()) WHERE token=$1", [token]);
  return new Response("unsubscribed", { status: 200 });
}
export async function GET(req) {
  const token = new URL(req.url).searchParams.get("token") || "";
  return Response.redirect(new URL(`/unsubscribe?token=${encodeURIComponent(token)}`, process.env.SITE_URL || req.url), 302);
}
