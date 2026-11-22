import { q } from "../../../lib/db";
import { clientIp, hit } from "../../../lib/ratelimit";
export const dynamic = "force-dynamic";
export const metadata = { title: "Confirm subscription", robots: { index: false, follow: false } };
export default async function Confirm({ searchParams }) {
  const token = String(searchParams.token || "");
  let row = null, limited = false;
  if (/^[a-f0-9]{16,128}$/.test(token)) {
    limited = !(await hit("confirm", clientIp(), 30, 600)).ok;
    if (!limited) [row] = await q("UPDATE subscribers SET confirmed=true, confirmed_at=COALESCE(confirmed_at,now()), unsubscribed_at=NULL WHERE token=$1 RETURNING email", [token]);
  }
  return (<main className="wrap page prose">
    {row ? (<><span className="eyebrow"><i />Confirmed</span><h1>You are <em>in.</em></h1>
      <p>{row.email} is confirmed. The next issue lands on Monday morning IST. Meanwhile, the <a href="/weekly">archive</a> has every issue so far.</p>
      <p><a className="btn" href="/weekly/latest">Read the latest issue <span>→</span></a></p></>)
      : (<><span className="eyebrow"><i />Link problem</span><h1>That link <em>did not work.</em></h1>
        <p>{limited ? "Too many tries from this network. Wait a few minutes and use the link again." : "It may be incomplete or already replaced by a newer one. Subscribe again and use the newest email."}</p>
        <p><a className="btn" href="/subscribe">Subscribe again <span>→</span></a></p></>)}
  </main>);
}
