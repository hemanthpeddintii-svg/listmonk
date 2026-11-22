// Applies db/schema.sql idempotently. Safe to run at every boot and while the app is live.
//   node scripts/migrate.mjs            (DATABASE_URL required; SCHEMA_PATH optional)
// Each statement runs on its own in autocommit mode with lock_timeout, and is retried when it
// cannot get its lock. This way a long-open transaction elsewhere can never make an ALTER TABLE
// queue up behind it and freeze every reader (an ALTER waiting for a lock blocks all later queries).
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import pg from "pg";

const here = path.dirname(fileURLToPath(import.meta.url));
const candidates = [process.env.SCHEMA_PATH, path.join(here, "../../db/schema.sql"), path.join(here, "../db/schema.sql"), "/app/db/schema.sql"].filter(Boolean);
const schemaFile = candidates.find((p) => fs.existsSync(p));
if (!schemaFile) { console.error("migrate: schema.sql not found, tried:", candidates.join(", ")); process.exit(1); }
if (!process.env.DATABASE_URL) { console.error("migrate: DATABASE_URL is not set"); process.exit(1); }

const LOCK_TIMEOUT = process.env.MIGRATE_LOCK_TIMEOUT || "5s";
const TRIES = Number(process.env.MIGRATE_TRIES || 12);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Split SQL into statements, honouring '...' strings, "..." identifiers, -- and /* */ comments and $tag$ ... $tag$ bodies.
function splitSql(sql) {
  const out = []; let cur = ""; let i = 0; const n = sql.length;
  while (i < n) {
    const c = sql[i], d = sql[i + 1];
    if (c === "-" && d === "-") { const e = sql.indexOf("\n", i); const j = e < 0 ? n : e; cur += sql.slice(i, j); i = j; continue; }
    if (c === "/" && d === "*") { const e = sql.indexOf("*/", i + 2); const j = e < 0 ? n : e + 2; cur += sql.slice(i, j); i = j; continue; }
    if (c === "'" || c === '"') { let j = i + 1; while (j < n) { if (sql[j] === c) { if (sql[j + 1] === c) { j += 2; continue; } break; } j++; } cur += sql.slice(i, j + 1); i = j + 1; continue; }
    if (c === "$") {
      const m = /^\$([A-Za-z_][A-Za-z0-9_]*)?\$/.exec(sql.slice(i, i + 64));
      if (m) { const tag = m[0]; const e = sql.indexOf(tag, i + tag.length); const j = e < 0 ? n : e + tag.length; cur += sql.slice(i, j); i = j; continue; }
    }
    if (c === ";") { if (cur.trim()) out.push(cur.trim()); cur = ""; i++; continue; }
    cur += c; i++;
  }
  if (cur.trim()) out.push(cur.trim());
  // drop statements that are only comments
  return out.filter((s) => s.replace(/--[^\n]*/g, "").trim());
}

const isLockErr = (e) => ["55P03", "40P01"].includes(e.code);   // lock_not_available, deadlock_detected

async function connectWithRetry() {
  for (let k = 1; ; k++) {
    const c = new pg.Client({ connectionString: process.env.DATABASE_URL, application_name: "gcc-migrate" });
    try { await c.connect(); return c; }
    catch (e) { try { await c.end(); } catch {} if (k >= 30) throw e; console.log(`migrate: database not ready (${e.code || e.message}), retry ${k}/30`); await sleep(2000); }
  }
}

const client = await connectWithRetry();
try {
  await client.query(`SET lock_timeout = '${LOCK_TIMEOUT}'`);
  await client.query("SET statement_timeout = '120s'");
  // Serialise concurrent migrators (several containers booting at once). Session-level, non-blocking poll.
  for (let k = 0; ; k++) {
    const { rows } = await client.query("SELECT pg_try_advisory_lock(727001) ok");
    if (rows[0].ok) break;
    if (k > 60) throw new Error("another migration has held the lock for over a minute");
    await sleep(1000);
  }
  const stmts = splitSql(fs.readFileSync(schemaFile, "utf8"));
  let waited = 0;
  for (const [idx, s] of stmts.entries()) {
    for (let t = 1; ; t++) {
      try { await client.query(s); break; }                       // autocommit: one statement, one implicit transaction
      catch (e) {
        if (isLockErr(e) && t < TRIES) { waited++; console.log(`migrate: statement ${idx + 1} waiting for a lock (try ${t}/${TRIES}): ${s.slice(0, 70).replace(/\s+/g, " ")}`); await sleep(Math.min(1000 * t, 8000)); continue; }
        console.error(`migrate: statement ${idx + 1} failed: ${e.message}\n${s.slice(0, 300)}`); throw e;
      }
    }
  }
  console.log(`migrate: applied ${stmts.length} statements from ${schemaFile}${waited ? ` (${waited} lock waits)` : ""}`);
  await client.query("SELECT pg_advisory_unlock(727001)");
} catch (e) { console.error("migrate: failed:", e.message); process.exitCode = 1; }
finally { await client.end(); }
