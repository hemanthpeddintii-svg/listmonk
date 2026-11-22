// Runs once when the server boots. In production, refuse to start with a missing or default JWT_SECRET:
// sessions are signed with it, so a guessable secret means anyone can forge an admin cookie.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs" || process.env.NODE_ENV !== "production") return;
  if (process.env.NEXT_PHASE === "phase-production-build") return;   // the build must not need real secrets
  const s = process.env.JWT_SECRET || "";
  if (!s || s === "dev-only-change-me") {
    // Next logs errors thrown from register() but keeps serving, so exit explicitly.
    console.error("FATAL: JWT_SECRET is missing or still the default. Set a long random value: openssl rand -hex 32");
    process.exit(1);
  }
  if (s.length < 16) console.warn("[security] JWT_SECRET is shorter than 16 characters; use `openssl rand -hex 32` in production.");
}
