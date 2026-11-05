import "./globals.css";
import { getUser } from "../lib/auth";
import { logout } from "./actions";
import Cursor from "../components/Cursor";
export const metadata = {
  metadataBase: new URL(process.env.SITE_URL || "http://localhost:3000"),
  title: { default: "GCC Intel India: news, trackers and a database of Global Capability Centers", template: "%s · GCC Intel India" },
  alternates: { types: { "application/rss+xml": [{ url: "/rss.xml", title: "GCC Intel news" }, { url: "/weekly/rss.xml", title: "The GCC Weekly" }] } },
  openGraph: { siteName: "GCC Intel India", type: "website" }, twitter: { card: "summary_large_image" },
  description: "Search every GCC in India: parent company, cities, headcount, tech stack and live hiring signals, refreshed weekly, news daily." };
export default async function Root({ children }) {
  const u = await getUser();
  return (<html lang="en"><body><a className="skip" href="#main">Skip to content</a><Cursor />
    {process.env.BILLING_MODE === "test" && <div className="testbar">TEST BUILD · payments disabled · plans switchable from Dashboard</div>}
    <header className="nav"><nav className="nav-in">
      <a className="logo" href="/"><i />gcc·intel</a>
      <div className="nav-links"><a href="/news">News</a>
      <details className="dd"><summary>Trackers</summary><div className="dd-menu"><a href="/expansions">Expansions</a><a href="/people">People moves</a><a href="/deals">Deals</a><a href="/policies">State policies</a><a href="/events">Events</a><a href="/cities">Cities</a></div></details>
      <a href="/reports">Reports</a><a href="/companies">Companies</a><a href="/jobs">Jobs</a><a href="/weekly">Weekly</a>
      </div><span className="sp" /><a href="/search" aria-label="Search" className="srch">Search</a>
      <details className="mnav"><summary>Menu</summary><div className="mnav-menu"><a href="/news">News</a><a href="/expansions">Expansions</a><a href="/people">People moves</a><a href="/deals">Deals</a><a href="/policies">Policies</a><a href="/reports">Reports</a><a href="/companies">Companies</a><a href="/jobs">Jobs</a><a href="/cities">Cities</a><a href="/weekly">Weekly</a><a href="/learn">What is a GCC?</a>{u ? <><a href="/dashboard">Dashboard</a>{u.role === "admin" && <a href="/admin">Admin</a>}</> : <a href="/login">Log in</a>}</div></details>
      {u ? (<>{u.role === "admin" && <a href="/admin">Admin</a>}<a href="/dashboard">Dashboard</a>
        <form action={logout}><button className="btn pill-ghost" style={{ background: "rgba(255,255,255,.12)", boxShadow: "none" }}>Log out</button></form></>)
        : (<><a href="/login">Log in</a><a className="btn" href="/signup">Start free <span>→</span></a></>)}
    </nav></header>
    <div id="main">{children}</div>
    <footer className="foot"><div className="wrap">
      <div className="mark">gcc·intel</div>
      <div className="foot-row"><span>The daily record of India&apos;s GCC boom. News daily, deep refresh weekly.</span>
        <span><a href="/news">News</a> · <a href="/expansions">Expansions</a> · <a href="/people">People</a> · <a href="/deals">Deals</a> · <a href="/policies">Policies</a> · <a href="/reports">Reports</a> · <a href="/methodology">Methodology</a> · <a href="/learn">What is a GCC?</a> · <a href="/pricing">Pricing</a> · <a href="/rss.xml">RSS</a></span></div></div></footer>
  </body></html>);
}
