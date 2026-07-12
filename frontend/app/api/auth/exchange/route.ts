import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

// Must match EXCHANGE_SECRET in backend/.env.
// Set this in Vercel environment variables (not exposed to the browser —
// server-only env var, no NEXT_PUBLIC_ prefix).
const EXCHANGE_SECRET = process.env.EXCHANGE_SECRET ?? "";

/**
 * GET /api/auth/exchange?relay=<relay_token>&next=/dashboard/<username>
 *
 * Server-side relay token exchange.  This route is called by the backend
 * OAuth callback redirect (never the browser directly with a session token).
 *
 * Flow:
 *  1. Backend /auth/callback issues a 2-minute relay token and redirects here.
 *  2. This route forwards the relay token to the backend /auth/exchange.
 *  3. Backend validates the relay token (type + expiry), issues a full
 *     session token, and responds with Set-Cookie.
 *  4. This route copies that Set-Cookie header onto the response to the
 *     browser (now on the Vercel origin) and redirects to the dashboard.
 *
 * The full 7-day session JWT is therefore never present in any URL, browser
 * history, or access log — only the short-lived relay token is, and it is
 * single-use by expiry (2 minutes).
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const relayToken = searchParams.get("relay");
  const next = searchParams.get("next") || "/";

  if (!relayToken) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${BACKEND_URL}/auth/exchange?relay=${encodeURIComponent(relayToken)}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
          // Pre-shared secret so /auth/exchange rejects calls that don't
          // originate from this Vercel deployment.  Defence-in-depth while
          // EC2 does not yet have TLS — the endpoint is not publicly
          // exploitable without this header.
          "X-Exchange-Secret": EXCHANGE_SECRET,
        },
      }
    );
  } catch {
    // Backend unreachable — send back to landing page rather than hanging.
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (!backendResponse.ok) {
    // Relay token invalid or expired — start over.
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Forward the session cookie set by the backend onto the Vercel origin.
  const setCookieHeader = backendResponse.headers.get("set-cookie");
  const redirectTarget = new URL(next, request.url);
  // Safety: only allow relative `next` paths to prevent open redirect.
  if (redirectTarget.origin !== new URL(request.url).origin) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  const response = NextResponse.redirect(redirectTarget);
  if (setCookieHeader) {
    response.headers.set("set-cookie", setCookieHeader);
  }
  return response;
}
