import { NextResponse, type NextRequest } from "next/server";

// Every page lives under /en, /hi or /ta so <html lang> and the dictionary follow the URL.
// A path without a language prefix is redirected, choosing from the browser's Accept-Language.
// The language code is not personal data; nothing else is read from the request.
const LANGUAGES = ["en", "hi", "ta"] as const;

function preferredLanguage(acceptLanguage: string | null): string {
  if (!acceptLanguage) return "en";
  const ranked = acceptLanguage
    .split(",")
    .map((part) => {
      const [tag, q] = part.trim().split(";q=");
      return { base: tag.toLowerCase().split("-")[0], q: q ? Number(q) : 1 };
    })
    .filter((x) => !Number.isNaN(x.q))
    .sort((a, b) => b.q - a.q);
  return ranked.find((x) => (LANGUAGES as readonly string[]).includes(x.base))?.base ?? "en";
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const first = pathname.split("/")[1] ?? "";
  if ((LANGUAGES as readonly string[]).includes(first)) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = `/${preferredLanguage(request.headers.get("accept-language"))}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Skip Next internals, /api (forwarded to the UnSeal API by the rewrite in next.config.ts, never
  // redirected to a language page) and any file with an extension (favicon, fonts, images).
  matcher: ["/((?!_next/|api(?:/|$)|.*\\..*).*)"],
};
