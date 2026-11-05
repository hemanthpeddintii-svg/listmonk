import { NextResponse } from "next/server";
// Cheap gate: bounce anonymous visitors from private pages (full check happens server-side).
export function middleware(req) {
  if (!req.cookies.get("gcc_session")) {
    const url = req.nextUrl.clone(); url.pathname = "/login"; url.search = `?next=${req.nextUrl.pathname}`;
    return NextResponse.redirect(url);
  }
}
export const config = { matcher: ["/dashboard/:path*", "/admin/:path*"] };
