// A stand-in for the UnSeal API behind the /api rewrite, used only by e2e/deploy.spec.ts. It
// echoes what reached it (method, path, Origin, Cookie, body size), so the test can check what
// the Next.js proxy forwards. It is not the API and holds no data.
import { createServer } from "node:http";

const PORT = Number(process.env.FAKE_API_PORT ?? 8100);

createServer((req, res) => {
  let received = 0;
  req.on("data", (chunk) => {
    received += chunk.length;
  });
  req.on("end", () => {
    const headers = { "content-type": "application/json" };
    if (req.method === "POST" && req.url === "/session") {
      // Shaped like the real cookie (ADR 0003); the value is a fixed fictional token.
      headers["set-cookie"] = "unseal_session=fictional-test-session; HttpOnly; Secure; SameSite=Lax; Path=/";
    }
    res.writeHead(200, headers);
    res.end(
      JSON.stringify({
        method: req.method,
        path: req.url,
        origin: req.headers.origin ?? null,
        cookie: req.headers.cookie ?? null,
        forwardedHost: req.headers["x-forwarded-host"] ?? null,
        contentLength: req.headers["content-length"] ?? null,
        received,
      }),
    );
  });
}).listen(PORT, "127.0.0.1");
