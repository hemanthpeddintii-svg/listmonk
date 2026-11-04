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
    <header className="nav"><nav className="nav-in">
      <a className="logo" href="/"><i />gcc·intel</a>
      <a href="/companies">Companies</a><a href="/pricing">Pricing</a>
      <span className="sp" />
      {u ? (<>{u.role === "admin" && <a href="/admin">Admin</a>}<a href="/dashboard">Dashboard</a>
        <form action={logout}><button className="btn pill-ghost" style={{ background: "rgba(255,255,255,.12)", boxShadow: "none" }}>Log out</button></form></>)
        : (<><a href="/login">Log in</a><a className="btn" href="/signup">Start free <span>→</span></a></>)}
    </nav></header>
    {children}
    <footer className="foot"><div className="wrap">
      <div className="mark">gcc·intel</div>
      <div className="foot-row"><span>Every Global Capability Center in India, refreshed every 72 hours.</span>
        <span><a href="/companies">Companies</a> · <a href="/pricing">Pricing</a> · <a href="/login">Log in</a></span></div></div></footer>
  </body></html>);
}
