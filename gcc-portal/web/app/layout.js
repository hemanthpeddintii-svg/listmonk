import "./globals.css";
import { getUser } from "../lib/auth";
import { logout } from "./actions";
import Cursor from "../components/Cursor";
export const metadata = {
  metadataBase: new URL(process.env.SITE_URL || "http://localhost:3000"),
  title: { default: "GCC Intel India – Database of 2,000+ Global Capability Centers", template: "%s · GCC Intel India" },
  description: "Search every GCC in India: parent company, cities, headcount, tech stack and live hiring signals, refreshed every 3 days." };
export default async function Root({ children }) {
  const u = await getUser();
  return (<html lang="en"><body><Cursor />
    {process.env.BILLING_MODE === "test" && <div className="testbar">TEST BUILD · payments disabled · plans switchable from Dashboard</div>}
    <header className="nav"><nav className="nav-in">
      <a className="logo" href="/"><i />gcc·intel</a>
      <a href="/news">News</a>
      <details className="dd"><summary>Trackers</summary><div className="dd-menu"><a href="/expansions">Expansions</a><a href="/people">People moves</a><a href="/deals">Deals</a><a href="/policies">State policies</a><a href="/events">Events</a><a href="/cities">Cities</a></div></details>
      <a href="/reports">Reports</a><a href="/companies">Companies</a><a href="/jobs">Jobs</a><a href="/weekly">Weekly</a>
      <span className="sp" /><a href="/search" aria-label="Search" className="srch">⌕ Search</a>
      {u ? (<>{u.role === "admin" && <a href="/admin">Admin</a>}<a href="/dashboard">Dashboard</a>
        <form action={logout}><button className="btn pill-ghost" style={{ background: "rgba(255,255,255,.12)", boxShadow: "none" }}>Log out</button></form></>)
        : (<><a href="/login">Log in</a><a className="btn" href="/signup">Start free <span>→</span></a></>)}
    </nav></header>
    {children}
    <footer className="foot"><div className="wrap">
      <div className="mark">gcc·intel</div>
      <div className="foot-row"><span>The daily record of India&apos;s GCC boom. News daily, deep refresh weekly.</span>
        <span><a href="/news">News</a> · <a href="/expansions">Expansions</a> · <a href="/people">People</a> · <a href="/deals">Deals</a> · <a href="/policies">Policies</a> · <a href="/reports">Reports</a> · <a href="/methodology">Methodology</a> · <a href="/learn">What is a GCC?</a> · <a href="/pricing">Pricing</a> · <a href="/rss.xml">RSS</a></span></div></div></footer>
  </body></html>);
}
