export const metadata = {
  title: "GCC Intel India – Database of 2,000+ Global Capability Centers",
  description: "Search every GCC in India: parent company, cities, headcount, tech stack, live hiring signals. Refreshed every 3 days." };
export default function Root({ children }) {
  return (<html lang="en"><body style={{fontFamily:"system-ui",maxWidth:960,margin:"0 auto",padding:16}}>
    <nav style={{display:"flex",gap:16}}><a href="/">GCC Intel</a><a href="/companies">Companies</a><a href="/pricing">Pricing</a><a href="/login">Log in</a></nav>
    {children}</body></html>);
}
