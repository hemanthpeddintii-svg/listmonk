// NEXT_DIST lets parallel builds use separate output dirs (e.g. NEXT_DIST=.next-qa).
// NEXT_STANDALONE=1 (set by the Dockerfile) emits a self-contained server in <distDir>/standalone.
const isDev = process.env.NODE_ENV !== "production";
const https = /^https:/i.test(process.env.SITE_URL || "");

// CSP notes: Next injects inline bootstrap scripts, so script-src needs 'unsafe-inline' (a nonce would force every page
// to render dynamically). JSON-LD <script type="application/ld+json"> blocks are data, not executed, so they are unaffected.
// img-src allows https: because company logos may come from any host; nothing else may load off-site.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(https && !isDev ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },   // browsers ignore it over plain http
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
];

module.exports = {
  distDir: process.env.NEXT_DIST || ".next",
  poweredByHeader: false,
  ...(process.env.NEXT_STANDALONE === "1" ? { output: "standalone" } : {}),
  experimental: { instrumentationHook: true },   // web/instrumentation.js: refuses to boot in production with a weak JWT_SECRET
  async headers() { return [{ source: "/:path*", headers: securityHeaders }]; },
};
