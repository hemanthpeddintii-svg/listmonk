export const metadata = { title: "Page not found" };
export default function NotFound() {
  return (<main className="wrap auth"><span className="eyebrow"><i />404</span><h1 style={{ fontSize: "clamp(48px,8vw,110px)" }}>This page is <em>not on the map.</em></h1>
    <p className="deck">The link may be old, or the story was removed. Try search, or start from the front page.</p>
    <p><a className="btn" href="/">Front page</a> <a className="btn ghost" href="/search">Search</a> <a className="btn ghost" href="/news">Latest news</a></p></main>);
}
