import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/", "/auth"];
const BACKEND_URL = "http://127.0.0.1:8000";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith("/auth"))) {
    return NextResponse.next();
  }

  const sessionCookie = request.cookies.get("devpulse_session")?.value;

  if (!sessionCookie) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  try {
    const res = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: { Cookie: `devpulse_session=${sessionCookie}` },
    });

    if (!res.ok) {
      return NextResponse.redirect(new URL("/", request.url));
    }

    return NextResponse.next();
  } catch {
    return NextResponse.redirect(new URL("/", request.url));
  }
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
