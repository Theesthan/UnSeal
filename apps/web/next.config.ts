import type { NextConfig } from "next";

/**
 * The browser calls /api/* on the web app's own origin and Next.js forwards it to the UnSeal API,
 * so the session cookie (HttpOnly, SameSite=Lax) is first-party wherever the two are hosted.
 * API_ORIGIN is server-side only (no NEXT_PUBLIC_ prefix) and is read when the app is built.
 */
function apiOrigin(): string {
  const raw = process.env.API_ORIGIN?.trim();
  if (!raw) {
    if (process.env.NODE_ENV === "production") {
      console.warn("[unseal] API_ORIGIN is not set: /api/* is forwarded to http://localhost:8000.");
    }
    return "http://localhost:8000";
  }
  const url = new URL(raw); // throws at build time on a malformed value
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("API_ORIGIN must be an http or https URL");
  }
  return url.origin;
}

const API_ORIGIN = apiOrigin();

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/:path*` }];
  },
  experimental: {
    // Self-hosted rewrites give up after 30 s by default. Reading a reply letter calls the model,
    // which may take up to 120 s plus retries (CLAUDE.md), so allow 180 s.
    proxyTimeout: 180_000,
    // Next.js buffers every proxied request body up to this size and silently cuts the rest
    // (default 10 MB), which hangs the API on a reply upload at its 10 MB limit plus the
    // multipart framing (POST /cases/{id}/reply/read). e2e/deploy.spec.ts guards this.
    proxyClientMaxBodySize: "11mb",
  },
};

export default nextConfig;
