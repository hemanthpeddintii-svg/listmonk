// First-boot data load: if the companies table is empty and SEED_DATA=1, load db/seed_data.sql.gz.
import pg from "pg"; import fs from "fs"; import zlib from "zlib";
const file = new URL("../db/seed_data.sql.gz", import.meta.url), alt = "db/seed_data.sql.gz";
const path = fs.existsSync(alt) ? alt : file;
if (process.env.SEED_DATA !== "1") process.exit(0);
const db = new pg.Client({ connectionString: process.env.DATABASE_URL, ssl: process.env.DATABASE_SSL === "1" ? { rejectUnauthorized: false } : undefined });
await db.connect();
const { rows: [{ n }] } = await db.query("SELECT count(*)::int n FROM companies");
if (n > 0) { console.log(`seed: skipped (companies already has ${n} rows)`); await db.end(); process.exit(0); }
if (!fs.existsSync(path)) { console.log("seed: no seed file found, skipping"); await db.end(); process.exit(0); }
const sql = zlib.gunzipSync(fs.readFileSync(path)).toString("utf8");
await db.query("BEGIN"); await db.query(sql); await db.query("COMMIT");
await db.query("SET search_path TO public");   // the dump clears search_path for the session
const { rows: [c] } = await db.query("SELECT (SELECT count(*) FROM companies)::int co,(SELECT count(*) FROM articles)::int arts");
console.log(`seed: loaded ${c.co} companies, ${c.arts} stories`); await db.end();
