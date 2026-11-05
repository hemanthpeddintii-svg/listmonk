import { redirect } from "next/navigation";
import { q } from "../../../lib/db";
export const dynamic = "force-dynamic";
export default async function Latest() {
  const [d] = await q("SELECT week_start::text ws FROM digests ORDER BY week_start DESC LIMIT 1").catch(() => []);
  redirect(d ? `/weekly/${d.ws}` : "/weekly");
}
