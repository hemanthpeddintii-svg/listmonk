import { q } from "../../lib/db";
import { clientIp, hit } from "../../lib/ratelimit";
export const dynamic = "force-dynamic";
export const metadata = { title: "Unsubscribe", robots: { index: false, follow: false } };
export default async function Unsub({ searchParams }) {
  const token = String(searchParams.token || "");
  let row = null, known = false;
  if (/^[a-f0-9]{16,128}$/.test(token) && (await hit("unsub", clientIp(), 30, 600)).ok) {
    [row] = await q("UPDATE subscribers SET unsubscribed_at=COALESCE(unsubscribed_at,now()) WHERE token=$1 RETURNING email", [token]);
    known = !!row;
  }
  return (<main className="wrap page prose">
    {known ? (<><span className="eyebrow"><i />Unsubscribed</span><h1>You are <em>off the list.</em></h1>
      <p>{row.email} will not get another issue. No confirmation email, no follow-ups.</p>
      <p className="mut">Clicked by mistake? <a href="/subscribe">Subscribe again</a>. The <a href="/weekly">archive</a> stays open to everyone.</p></>)
      : (<><span className="eyebrow"><i />Link problem</span><h1>We could not <em>find that link.</em></h1>
        <p>It may be incomplete. Every issue ends with a fresh unsubscribe link; use the one from your latest email, or reply to it and we will remove you by hand.</p></>)}
  </main>);
}
