// Tiny dependency-free SMTP sender (AUTH PLAIN/LOGIN, implicit TLS or STARTTLS). Configure with
// SMTP_URL=smtp://user:pass@host:587 (or smtps://...:465) or SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS, SMTP_FROM.
// SMTP_STARTTLS=0 disables the STARTTLS upgrade (local test sinks only).
import net from "net";
import tls from "tls";
import crypto from "crypto";

export function smtpConfig() {
  const url = (process.env.SMTP_URL || "").trim();
  let c = null;
  if (url) {
    const u = new URL(url);
    c = { host: u.hostname, port: Number(u.port) || (u.protocol === "smtps:" ? 465 : 587), user: decodeURIComponent(u.username), pass: decodeURIComponent(u.password), secure: u.protocol === "smtps:" };
  } else if (process.env.SMTP_HOST) {
    const port = Number(process.env.SMTP_PORT) || 587;
    c = { host: process.env.SMTP_HOST, port, user: process.env.SMTP_USER || "", pass: process.env.SMTP_PASS || "", secure: port === 465 || ["1", "true", "yes"].includes((process.env.SMTP_SECURE || "").toLowerCase()) };
  }
  if (!c) return null;
  c.starttls = !["0", "false", "no"].includes((process.env.SMTP_STARTTLS || "1").toLowerCase());
  c.from = process.env.SMTP_FROM || `GCC Intel <noreply@${c.host.replace(/^smtp\./, "")}>`;
  return c;
}
export const smtpConfigured = () => !!smtpConfig();

// One command/response conversation. A reply is complete when its last line is "NNN text" (not "NNN-text").
function conn(c) {
  return new Promise((resolve, reject) => {
    let sock = c.secure ? tls.connect({ host: c.host, port: c.port, servername: c.host }) : net.connect({ host: c.host, port: c.port });
    let buf = "", err = null, pending = null;
    const complete = () => { const ls = buf.split("\r\n").filter(Boolean); return buf.endsWith("\r\n") && ls.length && /^\d{3} /.test(ls[ls.length - 1]); };
    const pump = () => {
      if (!pending) return;
      if (err) { const p = pending; pending = null; p.rej(err); }
      else if (complete()) { const p = pending, t = buf; pending = null; buf = ""; p.res(t); }
    };
    const attach = (s) => {
      s.setTimeout(20000, () => s.destroy(new Error("smtp timeout")));
      s.on("data", (d) => { buf += d.toString("utf8"); pump(); });
      s.on("error", (e) => { err = e; pump(); });
      s.on("close", () => { if (!err) err = new Error("smtp connection closed"); pump(); });
    };
    attach(sock);
    const api = {
      read: () => new Promise((res, rej) => { pending = { res, rej }; pump(); }),
      async cmd(line, ok) { if (line !== null) sock.write(line + "\r\n"); const r = await api.read(); if (!r.startsWith(String(ok))) throw new Error(`smtp: expected ${ok}, got ${r.trim().slice(0, 120)}`); return r; },
      async upgrade() {
        sock.removeAllListeners("data"); sock.removeAllListeners("close"); sock.removeAllListeners("error");
        const raw = sock; buf = "";
        sock = tls.connect({ socket: raw, servername: c.host }); attach(sock);
        await new Promise((res, rej) => { sock.once("secureConnect", res); sock.once("error", rej); });
      },
      raw: (x) => sock.write(x),
      close: () => { try { sock.end(); } catch {} },
    };
    sock.once(c.secure ? "secureConnect" : "connect", () => resolve(api));
    sock.once("error", reject);
  });
}

const b64 = (s) => Buffer.from(s, "utf8").toString("base64");
const enc = (s) => (/^[\x20-\x7e]*$/.test(s) ? s : `=?UTF-8?B?${b64(s)}?=`);
const addr = (s) => (/<([^>]+)>/.exec(s) || [null, s])[1].trim();

export async function sendMail({ to, subject, text, html, headers = {} }) {
  const c = smtpConfig();
  if (!c) throw new Error("SMTP not configured");
  if (/[\r\n]/.test(to + subject)) throw new Error("bad header value");
  const api = await conn(c);
  try {
    await api.cmd(null, 220);
    const host = process.env.SITE_URL ? new URL(process.env.SITE_URL).hostname : "localhost";
    let ehlo = await api.cmd(`EHLO ${host}`, 250);
    if (!c.secure && c.starttls && /STARTTLS/i.test(ehlo)) { await api.cmd("STARTTLS", 220); await api.upgrade(); ehlo = await api.cmd(`EHLO ${host}`, 250); }
    if (c.user) {
      if (/AUTH[^\n]*PLAIN/i.test(ehlo)) await api.cmd("AUTH PLAIN " + b64(`\0${c.user}\0${c.pass}`), 235);
      else { await api.cmd("AUTH LOGIN", 334); await api.cmd(b64(c.user), 334); await api.cmd(b64(c.pass), 235); }
    }
    await api.cmd(`MAIL FROM:<${addr(c.from)}>`, 250);
    await api.cmd(`RCPT TO:<${addr(to)}>`, 250);
    await api.cmd("DATA", 354);
    const boundary = "b" + crypto.randomBytes(12).toString("hex");
    const hdr = { From: c.from, To: to, Subject: enc(subject), Date: new Date().toUTCString(), "Message-ID": `<${crypto.randomBytes(12).toString("hex")}@${host}>`, "MIME-Version": "1.0", ...headers };
    const body = html
      ? [`--${boundary}`, "Content-Type: text/plain; charset=utf-8", "Content-Transfer-Encoding: base64", "", b64(text).replace(/(.{76})/g, "$1\r\n"), `--${boundary}`, "Content-Type: text/html; charset=utf-8", "Content-Transfer-Encoding: base64", "", b64(html).replace(/(.{76})/g, "$1\r\n"), `--${boundary}--`, ""].join("\r\n")
      : [b64(text).replace(/(.{76})/g, "$1\r\n"), ""].join("\r\n");
    hdr["Content-Type"] = html ? `multipart/alternative; boundary="${boundary}"` : "text/plain; charset=utf-8";
    if (!html) hdr["Content-Transfer-Encoding"] = "base64";
    const head = Object.entries(hdr).map(([k, v]) => `${k}: ${v}`).join("\r\n");
    api.raw(head + "\r\n\r\n" + body + "\r\n.\r\n");
    await api.cmd(null, 250);
    await api.cmd("QUIT", 221).catch(() => {});
  } finally { api.close(); }
}

export const siteUrl = () => (process.env.SITE_URL || "http://localhost:3000").replace(/\/$/, "");
