import "./globals.css";
import { getUser } from "../lib/auth";
import { logout } from "./actions";
export const metadata = {
  metadataBase: new URL(process.env.SITE_URL || "http://localhost:3000"),
  title: { default: "GCC Intel India – Database of 2,000+ Global Capability Centers", template: "%s · GCC Intel India" },
  description: "Search every GCC in India: parent company, cities, headcount, tech stack and live hiring signals, refreshed every 3 days." };
export default async function Root({ children }) {
  const u = await getUser();
  return (<html lang="en"><body>
    <header className="nav"><div className="wrap">
      <a className="logo" href="/">GCC Intel</a>
      <a href="/companies">Companies</a><a href="/pricing">Pricing</a>
      <span className="sp" />
      {u ? (<>{u.role === "admin" && <a href="/admin">Admin</a>}<a href="/dashboard">Dashboard</a>
        <form action={logout}><button className="btn ghost">Log out</button></form></>)
        : (<><a href="/login">Log in</a><a className="btn" href="/signup">Get started free</a></>)}
    </div></header>
    <div className="wrap">{children}
      <footer>© {new Date().getFullYear()} GCC Intel India · Data refreshed every 3 days · <a href="/pricing">Pricing</a></footer></div>
  </body></html>);
}
