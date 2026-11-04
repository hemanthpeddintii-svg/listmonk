import TestPlanSwitch from "../../components/TestPlanSwitch";
import { PLANS } from "../../lib/plans";
import { getUser } from "../../lib/auth";
export const metadata = { title: "Pricing" };
const feat = (p) => [`${p.maxRows >= 1000 ? "Full" : p.maxRows} companies in search`, `${p.jobs} latest jobs per company`,
  p.export ? "CSV export" : "No export", p.alerts ? `${p.alerts} saved-search alerts` : "No alerts", `${p.saved} saved companies`];
export default async function Pricing() {
  const u = await getUser();
  return (<main className="wrap page"><h1>Pricing</h1><p className="mut">Start free. Upgrade when you need the full database.</p>
    <div className="grid plans">{Object.entries(PLANS).map(([k, p]) => (
      <div key={k} className={"card" + (k === "pro" ? " hl" : "")}><h3>{p.label}</h3><h2>{p.price}</h2>
        <ul>{feat(p).map(f => <li key={f}>{f}</li>)}</ul>
        {k === "free" ? <a className="btn ghost" href={u ? "/dashboard" : "/signup"}>Start free</a>
          : <a className="btn" href={process.env.BILLING_MODE === "test" ? (u ? "/dashboard" : "/signup") : `/dashboard?upgrade=${k}`}>{process.env.BILLING_MODE === "test" ? `Try ${p.label} (test)` : `Choose ${p.label}`}</a>}</div>))}</div>
    {u && <TestPlanSwitch current={u.plan} />}<p className="mut">Payments: Razorpay (India) / Stripe (international) — webhook at <code>/api/billing/webhook</code>.</p></main>);
}
