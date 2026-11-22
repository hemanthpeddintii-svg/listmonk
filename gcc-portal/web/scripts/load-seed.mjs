// First-boot data load: if the companies table is empty and SEED_DATA=1, load db/seed_data.sql.gz.
import pg from "pg"; import fs from "fs"; import zlib from "zlib";
import { fileURLToPath } from "url"; import nodePath from "path";
const here = nodePath.dirname(fileURLToPath(import.meta.url));
// container: /app/scripts + /app/db ; repo: gcc-portal/web/scripts + gcc-portal/db
const path = [process.env.SEED_FILE, nodePath.join(here, "../db/seed_data.sql.gz"), nodePath.join(here, "../../db/seed_data.sql.gz"), "db/seed_data.sql.gz"].filter(Boolean).find((f) => fs.existsSync(f));
if (process.env.SEED_DATA !== "1") process.exit(0);
const db = new pg.Client({ connectionString: process.env.DATABASE_URL, ssl: process.env.DATABASE_SSL === "1" ? { rejectUnauthorized: false } : undefined });
await db.connect();
const { rows: [{ n }] } = await db.query("SELECT count(*)::int n FROM companies");
if (n > 0) { console.log(`seed: skipped (companies already has ${n} rows)`); await db.end(); process.exit(0); }
if (!path) { console.log("seed: no seed file found, skipping"); await db.end(); process.exit(0); }
const sql = zlib.gunzipSync(fs.readFileSync(path)).toString("utf8");
await db.query("BEGIN"); await db.query(sql); await db.query("COMMIT");
await db.query("SET search_path TO public");   // the dump clears search_path for the session
const { rows: [c] } = await db.query("SELECT (SELECT count(*) FROM companies)::int co,(SELECT count(*) FROM articles)::int arts");
console.log(`seed: loaded ${c.co} companies, ${c.arts} stories`); await db.end();
