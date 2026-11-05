// Creates demo accounts: node scripts/seed-demo.mjs   (needs DATABASE_URL)
import pg from "pg"; import bcrypt from "bcryptjs";
const db = new pg.Client({ connectionString: process.env.DATABASE_URL }); await db.connect();
const h = await bcrypt.hash("demo12345", 10);
for (const [email, name, role, plan] of [["admin@gccintel.test", "Demo Admin", "admin", "team"], ["pro@gccintel.test", "Demo Pro", "user", "pro"], ["free@gccintel.test", "Demo Free", "user", "free"]])
  await db.query(`INSERT INTO users(email,name,password_hash,role,plan,plan_expires_at) VALUES($1,$2,$3,$4,$5,CASE WHEN $5='free' THEN NULL ELSE now()+interval '365 days' END)
    ON CONFLICT(email) DO UPDATE SET password_hash=$3, role=$4, plan=$5, plan_expires_at=EXCLUDED.plan_expires_at`, [email, name, h, role, plan]);
console.log("demo users ready"); await db.end();
