import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SignJWT, jwtVerify } from "jose";
import bcrypt from "bcryptjs";
import { q } from "./db";
import { planOf, effectivePlan } from "./plans";

const secret = () => new TextEncoder().encode(process.env.JWT_SECRET || "dev-only-change-me");
const COOKIE = "gcc_session";

export const hash = (pw) => bcrypt.hash(pw, 10);
export const verify = (pw, h) => (h ? bcrypt.compare(pw, h) : false);

export async function startSession(userId) {
  const token = await new SignJWT({ uid: userId }).setProtectedHeader({ alg: "HS256" })
    .setExpirationTime("30d").sign(secret());
  cookies().set(COOKIE, token, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 24 * 30 });
}
export const endSession = () => cookies().delete(COOKIE);

export async function getUser() {
  const t = cookies().get(COOKIE)?.value;
  if (!t) return null;
  try {
    const { payload } = await jwtVerify(t, secret());
    const [u] = await q("SELECT id,email,name,role,plan,plan_expires_at FROM users WHERE id=$1", [payload.uid]);
    if (!u) return null;
    u.plan = effectivePlan(u);
    return u;
  } catch { return null; }
}
export async function requireUser() { const u = await getUser(); if (!u) redirect("/login"); return u; }
export async function requireAdmin() { const u = await requireUser(); if (u.role !== "admin") redirect("/dashboard"); return u; }
export { planOf };
