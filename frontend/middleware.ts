import { NextRequest, NextResponse } from "next/server";

/**
 * Auth guard for dashboard routes.
 *
 * Token interception was removed as part of the relay token security fix
 * (2026-07-12).  Session cookies are now set server-side by
 * /api/auth/exchange, which validates the short-lived relay token with the
 * backend before issuing the cookie on the Vercel origin.
 * See: app/api/auth/exchange/route.ts
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Protect dashboard routes — redirect to landing if no session cookie.
  if (pathname.startsWith("/dashboard")) {
    const sessionCookie = request.cookies.get("devpulse_session")?.value;
    if (!sessionCookie) {
      return NextResponse.redirect(new URL("/", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
