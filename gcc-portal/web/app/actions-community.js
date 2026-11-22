"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { q } from "../lib/db";
import { getUser } from "../lib/auth";
import { CITY_LIST } from "../lib/content";
import { TOPICS, TARGETS } from "../lib/community";

const refresh = () => revalidatePath("/", "layout");
const loginNext = (next) => "/login?next=" + encodeURIComponent(String(next || "/dashboard").startsWith("/") ? String(next || "/dashboard") : "/dashboard");

/* ---------- comments ---------- */
const MAX = 2000;
const cleanBody = (s) => String(s || "").replace(/\r\n?/g, "\n").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F‪-‮⁦-⁩]/g, "").replace(/\n{3,}/g, "\n\n").trim();

async function targetExists(type, id) {
  const table = { article: "articles", company: "companies", expansion: "expansions" }[type];
  if (!table) return false;
  return (await q(`SELECT 1 FROM ${table} WHERE id=$1`, [id])).length > 0;
}

export async function postComment(prev, fd) {
  const u = await getUser();
  if (!u) return { error: "Log in to join the discussion." };
  const type = String(fd.get("targetType")), id = Number(fd.get("targetId"));
  const body = cleanBody(fd.get("body"));
  if (!TARGETS.includes(type) || !Number.isInteger(id) || id < 1 || !(await targetExists(type, id))) return { error: "This page can't take comments." };
  if (!body) return { error: "Write something first." };
  if (body.length > MAX) return { error: `Keep it under ${MAX} characters (this is ${body.length}).` };
  let parent = null;
  const pid = Number(fd.get("parentId")) || null;
  if (pid) {
    const [p] = await q("SELECT id,parent_id,target_type,target_id,deleted,reports FROM comments WHERE id=$1", [pid]);
    if (!p || p.target_type !== type || p.target_id !== id || p.deleted) return { error: "The comment you're replying to is gone." };
    parent = p.parent_id || p.id;           // replies stay one level deep: answering a reply attaches to its thread
  }
  try {
    await q("INSERT INTO comments(user_id,target_type,target_id,parent_id,body) VALUES($1,$2,$3,$4,$5)", [u.id, type, id, parent, body]);
  } catch (e) {
    if (/rate_limit_15s/.test(e.message)) return { error: "Slow down. One comment every 15 seconds, try again in a moment." };
    if (/rate_limit_hour/.test(e.message)) return { error: "That's 20 comments in the last hour, the limit. Come back a little later." };
    throw e;
  }
  refresh();
  return { ok: true, n: Date.now() };
}

export async function deleteComment(fd) {
  const u = await getUser(); if (!u) redirect("/login");
  const id = Number(fd.get("id"));
  // Soft delete + blank the text, so replies keep their place in the thread but the words are gone.
  await q("UPDATE comments SET deleted=true, body='' WHERE id=$1 AND NOT deleted AND (user_id=$2 OR $3)", [id, u.id, u.role === "admin"]);
  refresh();
}

export async function reportComment(fd) {
  const u = await getUser(); if (!u) redirect(loginNext(fd.get("next")));
  const id = Number(fd.get("id"));
  await q(`WITH ins AS (
      INSERT INTO comment_reports(comment_id,user_id) SELECT c.id,$2 FROM comments c WHERE c.id=$1 AND c.user_id<>$2 AND NOT c.deleted
      ON CONFLICT DO NOTHING RETURNING 1)
    UPDATE comments SET reports = reports + 1 WHERE id=$1 AND EXISTS (SELECT 1 FROM ins)`, [id, u.id]);
  refresh();
}

/* ---------- votes ---------- */
export async function toggleVote(fd) {
  const u = await getUser(); if (!u) redirect(loginNext(fd.get("next")));
  const id = Number(fd.get("articleId"));
  if (!Number.isInteger(id) || id < 1) return;
  const del = await q("DELETE FROM votes WHERE user_id=$1 AND article_id=$2 RETURNING 1", [u.id, id]);
  if (!del.length) await q("INSERT INTO votes(user_id,article_id) SELECT $1,id FROM articles WHERE id=$2 ON CONFLICT DO NOTHING", [u.id, id]);
  refresh();
}

/* ---------- follows ---------- */
export async function toggleFollow(fd) {
  const u = await getUser(); if (!u) redirect(loginNext(fd.get("next")));
  const kind = String(fd.get("kind")), value = String(fd.get("value") || "").trim().slice(0, 80);
  if (!["company", "city", "topic"].includes(kind) || !value) return;
  if (kind === "topic" && !TOPICS.includes(value)) return;
  if (kind === "city" && !CITY_LIST.includes(value) && !(await q("SELECT 1 FROM articles WHERE city=$1 LIMIT 1", [value])).length) return;
  if (kind === "company" && !(/^\d+$/.test(value) && (await q("SELECT 1 FROM companies WHERE id=$1", [Number(value)])).length)) return;
  const del = await q("DELETE FROM follows WHERE user_id=$1 AND kind=$2 AND value=$3 RETURNING 1", [u.id, kind, value]);
  if (!del.length) {
    const [{ n }] = await q("SELECT count(*)::int n FROM follows WHERE user_id=$1", [u.id]);
    if (n >= 200) return;
    await q("INSERT INTO follows(user_id,kind,value) VALUES($1,$2,$3) ON CONFLICT DO NOTHING", [u.id, kind, value]);
  }
  refresh();
}
