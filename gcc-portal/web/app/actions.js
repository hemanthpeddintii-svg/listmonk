"use server";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { q } from "../lib/db";
import { hash, verify, startSession, endSession, getUser, requireUser, requireAdmin } from "../lib/auth";
import { planOf } from "../lib/plans";
import { parseCsv } from "../lib/csv";

const emailOk = (e) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e);

export async function signup(prev, fd) {
  const email = String(fd.get("email") || "").trim().toLowerCase();
  const pw = String(fd.get("password") || "");
  const name = String(fd.get("name") || "").trim();
  if (!emailOk(email)) return { error: "Enter a valid email." };
  if (pw.length < 8) return { error: "Password must be at least 8 characters." };
  const admins = (process.env.ADMIN_EMAILS || "").toLowerCase().split(",").map(s => s.trim());
  try {
    const [u] = await q(
      "INSERT INTO users(email,name,password_hash,role) VALUES($1,$2,$3,$4) RETURNING id",
      [email, name, await hash(pw), admins.includes(email) ? "admin" : "user"]);
    await startSession(u.id);
  } catch (e) {
    if (e.code === "23505") return { error: "An account with this email already exists." };
    throw e;
  }
  redirect("/dashboard");
}

export async function login(prev, fd) {
  const email = String(fd.get("email") || "").trim().toLowerCase();
  const [u] = await q("SELECT id,password_hash FROM users WHERE email=$1", [email]);
  if (!u || !(await verify(String(fd.get("password") || ""), u.password_hash)))
    return { error: "Wrong email or password." };
  await startSession(u.id);
  redirect(String(fd.get("next") || "/dashboard").startsWith("/") ? String(fd.get("next") || "/dashboard") : "/dashboard");
}

export async function logout() { endSession(); redirect("/"); }

export async function captureLead(prev, fd) {
  const email = String(fd.get("email") || "").trim().toLowerCase();
  if (!emailOk(email)) return { error: "Enter a valid email." };
  await q("INSERT INTO leads(email,source) VALUES($1,'landing') ON CONFLICT DO NOTHING", [email]);
  return { ok: "Thanks! We'll be in touch." };
}

export async function toggleSave(companyId) {
  const u = await requireUser();
  const del = await q("DELETE FROM saved_companies WHERE user_id=$1 AND company_id=$2 RETURNING 1", [u.id, companyId]);
  if (!del.length) {
    const [{ n }] = await q("SELECT count(*)::int n FROM saved_companies WHERE user_id=$1", [u.id]);
    if (n >= planOf(u).saved) return;           // plan limit
    await q("INSERT INTO saved_companies(user_id,company_id) VALUES($1,$2)", [u.id, companyId]);
  }
  revalidatePath("/companies"); revalidatePath(`/companies/${companyId}`); revalidatePath("/dashboard");
}

export async function saveSearch(prev, fd) {
  const u = await requireUser();
  const p = planOf(u);
  const [{ n }] = await q("SELECT count(*)::int n FROM saved_searches WHERE user_id=$1", [u.id]);
  if (p.alerts === 0) return { error: "Saved alerts need a Pro plan." };
  if (n >= p.alerts) return { error: "Alert limit reached." };
  const query = { q: fd.get("q") || "", city: fd.get("city") || "", industry: fd.get("industry") || "" };
  await q("INSERT INTO saved_searches(user_id,name,query,alert) VALUES($1,$2,$3,true)",
    [u.id, String(fd.get("name") || "My search"), query]);
  revalidatePath("/dashboard");
  return { ok: "Saved." };
}

// Admin: bulk import companies from CSV (name,domain,parent_company,hq_country,cities,industry,careers_url,...)
export async function importCompanies(prev, fd) {
  await requireAdmin();
  const file = fd.get("file");
  if (!file || !file.size) return { error: "Choose a CSV file." };
  const rows = parseCsv(await file.text());
  const [run] = await q("INSERT INTO ingestion_runs(kind,rows_in) VALUES('csv_import',$1) RETURNING id", [rows.length]);
  let ok = 0;
  for (const r of rows) {
    if (!r.name) continue;
    const cities = (r.cities || "").split(/[;|]/).map(s => s.trim()).filter(Boolean);
    const stack = (r.tech_stack || "").split(/[;|]/).map(s => s.trim()).filter(Boolean);
    await q(
      `INSERT INTO companies(name,domain,parent_company,hq_country,india_cities,industry,gcc_function,
         india_headcount_range,year_established,tech_stack,careers_url,source)
       VALUES($1,NULLIF($2,''),$3,$4,$5,$6,$7,$8,NULLIF($9,'')::int,$10,$11,'csv_import')
       ON CONFLICT (domain) DO UPDATE SET
         parent_company=COALESCE(EXCLUDED.parent_company,companies.parent_company),
         india_cities=EXCLUDED.india_cities, industry=COALESCE(EXCLUDED.industry,companies.industry)`,
      [r.name, (r.domain || "").toLowerCase(), r.parent_company || null, r.hq_country || null, cities,
       r.industry || null, r.gcc_function || null, r.india_headcount_range || null, r.year_established || "", stack, r.careers_url || null]);
    ok++;
  }
  await q("UPDATE ingestion_runs SET finished_at=now(), rows_ok=$2 WHERE id=$1", [run.id, ok]);
  revalidatePath("/admin"); revalidatePath("/companies");
  return { ok: `Imported ${ok} of ${rows.length} rows.` };
}

// Admin: change a user's plan manually (until payment provider is wired).
export async function setPlan(fd) {
  await requireAdmin();
  const plan = String(fd.get("plan"));
  if (!["free", "pro", "team"].includes(plan)) return;
  const days = plan === "free" ? null : 30;
  await q("UPDATE users SET plan=$2, plan_expires_at = CASE WHEN $3::int IS NULL THEN NULL ELSE now() + ($3::int||' days')::interval END WHERE id=$1",
    [Number(fd.get("id")), plan, days]);
  revalidatePath("/admin");
}
