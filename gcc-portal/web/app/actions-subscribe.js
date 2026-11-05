"use server";
import crypto from "crypto";
import { q } from "../lib/db";
import { CITY_LIST } from "../lib/content";
import { clientIp, hit, tooMany } from "../lib/ratelimit";
import { smtpConfigured, sendMail, siteUrl } from "../lib/mail";
import { TOPICS } from "../lib/subscribers";

const emailOk = (e) => e.length <= 254 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e);
const testMode = () => process.env.BILLING_MODE === "test" || process.env.NODE_ENV !== "production";

async function sendConfirm(email, token) {
  const url = `${siteUrl()}/subscribe/confirm?token=${token}`;
  if (!smtpConfigured()) { console.log(`[subscribe] SMTP not configured. Confirm link for ${email}: ${url}`); return { url, sent: false }; }
  await sendMail({
    to: email, subject: "Confirm your subscription to The GCC Weekly",
    text: `Confirm your subscription to The GCC Weekly (one email every Monday morning IST):\n\n${url}\n\nIf you did not ask for this, ignore this message and nothing will be sent.\n`,
    html: `<div style="font:16px/1.5 Georgia,serif;color:#121212;max-width:520px"><p>Confirm your subscription to <b>The GCC Weekly</b>, one email every Monday morning IST.</p><p><a href="${url}" style="background:#ff4b1f;color:#fff;padding:10px 20px;border-radius:99px;text-decoration:none;font:700 14px Helvetica,Arial,sans-serif;border:2px solid #121212">Confirm subscription</a></p><p style="color:#6b655b;font-size:13px">If you did not ask for this, ignore this message and nothing will be sent.</p></div>`,
  });
  return { url, sent: true };
}

export async function subscribe(prev, fd) {
  // Honeypot: real people never see this field. Pretend success so bots learn nothing.
  if (String(fd.get("website") || "").trim()) return { ok: "Check your inbox to confirm." };
  const email = String(fd.get("email") || "").trim().toLowerCase();
  if (!emailOk(email)) return { error: "Enter a valid email address." };
  const ip = clientIp();
  const r1 = await hit("sub-ip", ip, 5, 3600); if (!r1.ok) return tooMany(r1);
  const r2 = await hit("sub-email", email, 3, 3600); if (!r2.ok) return tooMany(r2);
  const valid = new Set(TOPICS.map(t => t[0]));
  const topics = [...new Set(fd.getAll("topics").map(String))].filter(t => valid.has(t));
  const cities = [...new Set(fd.getAll("cities").map(String))].filter(c => CITY_LIST.includes(c));
  const token = crypto.randomBytes(24).toString("hex");
  const [ex] = await q("SELECT id,confirmed,unsubscribed_at FROM subscribers WHERE email=$1", [email]);
  if (ex && ex.confirmed && !ex.unsubscribed_at)    // already active: never touch their prefs from an unauthenticated form
    return { ok: testMode() ? "That address is already subscribed. Use the link in any issue to change preferences." : "Check your inbox to confirm." };
  if (!ex) await q("INSERT INTO subscribers(email,topics,cities,token,source) VALUES($1,$2,$3,$4,'web')", [email, topics, cities, token]);
  else await q("UPDATE subscribers SET topics=$2,cities=$3,token=$4,confirmed=false,confirmed_at=NULL,unsubscribed_at=NULL WHERE id=$1", [ex.id, topics, cities, token]);
  try {
    const { url, sent } = await sendConfirm(email, token);
    if (!sent && testMode()) return { ok: "TEST MODE: email delivery is not configured, so here is your confirmation link.", confirmUrl: url };
    return { ok: "Check your inbox to confirm." };
  } catch (e) {
    console.error("[subscribe] confirmation email failed:", e.message);
    return { error: "We could not send the confirmation email. Try again in a few minutes." };
  }
}
