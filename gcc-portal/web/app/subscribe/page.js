import SubscribeForm from "./SubscribeForm";
import { css } from "./styles";
import { q } from "../../lib/db";
import { CITY_LIST } from "../../lib/content";
import { TOPICS } from "../../lib/subscribers";
export const dynamic = "force-dynamic";
export const metadata = {
  title: "Subscribe to The GCC Weekly",
  description: "One email every Monday morning IST: new and expanded GCCs in India, leadership moves, deals, policy and who is hiring. Pick your topics and cities.",
  alternates: { canonical: "/subscribe" },
};
export default async function Subscribe() {
  const [latest] = await q("SELECT week_start::text ws, title FROM digests ORDER BY week_start DESC LIMIT 1").catch(() => []);
  return (<main className="wrap page"><style dangerouslySetInnerHTML={{ __html: css }} />
    <span className="eyebrow"><i />Mondays, 7:00 IST</span>
    <h1>The GCC <em>Weekly.</em></h1>
    <div className="sub-grid">
      <div className="card" style={{ background: "#fff" }}>
        <SubscribeForm topics={TOPICS} cities={CITY_LIST} />
        <p className="mut" style={{ fontSize: 13, marginBottom: 0 }}>We email you a link to confirm, then one issue a week. Every issue has a one-click unsubscribe. We do not share addresses.</p>
      </div>
      <div className="prose">
        <p>One email, built from the database each Monday: which centres opened or expanded, who got hired into the top jobs, what was funded, which state changed its policy, and which companies posted the most roles.</p>
        <p>Every item links to the original source. Pick topics and cities and you only get those sections; leave them empty for the full issue.</p>
        <p><a href="/weekly">Read the archive</a>{latest && <> or open the <a href={`/weekly/${latest.ws}`}>latest issue</a></>}. There is also an <a href="/rss.xml">RSS feed</a> of stories and a <a href="/weekly/rss.xml">feed of issues</a>.</p>
      </div>
    </div></main>);
}
