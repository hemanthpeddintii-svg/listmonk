import pg from "pg";
const g = globalThis;
export const pool = g.__pool ?? (g.__pool = new pg.Pool({ connectionString: process.env.DATABASE_URL }));
export const q = (text, params) => pool.query(text, params).then(r => r.rows);
