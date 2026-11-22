import crypto from "crypto";
import { q } from "../../../../lib/db";
// Provider-agnostic webhook: POST JSON {event_id,email,plan,amount_minor,currency,status,provider}
// signed with HMAC-SHA256(BILLING_WEBHOOK_SECRET, rawBody) in header x-signature.
// Map Razorpay/Stripe payloads into this shape (or add provider-specific verification here).
export async function POST(req) {
  const raw = await req.text();
  const secret = process.env.BILLING_WEBHOOK_SECRET;
  if (!secret) return new Response("webhook not configured", { status: 503 });
  const sig = req.headers.get("x-signature") || "";
  const good = crypto.createHmac("sha256", secret).update(raw).digest("hex");
  if (sig.length !== good.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(good))) return new Response("bad signature", { status: 401 });
  const e = JSON.parse(raw);
  if (!["pro", "team"].includes(e.plan)) return new Response("bad plan", { status: 400 });
  const [u] = await q("SELECT id FROM users WHERE email=lower($1)", [e.email]);
  const dup = await q("INSERT INTO payments(user_id,provider,provider_ref,plan,amount_minor,currency,status) VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (provider_ref) DO NOTHING RETURNING id",
    [u?.id ?? null, e.provider, e.event_id, e.plan, e.amount_minor, e.currency, e.status]);
  if (dup.length && u && e.status === "paid")
    await q("UPDATE users SET plan=$2, plan_expires_at=GREATEST(COALESCE(plan_expires_at,now()),now())+interval '30 days' WHERE id=$1", [u.id, e.plan]);
  return Response.json({ ok: true });
}
