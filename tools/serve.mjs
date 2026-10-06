import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../", import.meta.url)));
const port = Number(process.env.PORT || 4173);
const webFiles = new Set(["index.html", "styles.css", "app.js", "config.js"]);
const mimeTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
]);

const server = createServer(async (request, response) => {
  const pathname = new URL(request.url || "/", "http://localhost").pathname;
  let requestedPath;
  try {
    requestedPath = decodeURIComponent(pathname === "/" ? "/index.html" : pathname);
  } catch {
    response.writeHead(400).end("Invalid path");
    return;
  }

  const filePath = resolve(root, `.${requestedPath}`);
  if (filePath !== root && !filePath.startsWith(`${root}${sep}`)) {
    response.writeHead(403).end("Forbidden");
    return;
  }
  const relativePath = requestedPath.replace(/^\/+/, "");
  const isAllowedWebFile =
    webFiles.has(relativePath) ||
    (/^src\/[a-zA-Z0-9_-]+\.js$/.test(relativePath) && filePath.startsWith(resolve(root, "src") + sep));
  if (!isAllowedWebFile) {
    response.writeHead(404).end("Not found");
    return;
  }

  try {
    const body = await readFile(filePath);
    response.writeHead(200, {
      "Content-Type": mimeTypes.get(extname(filePath)) || "application/octet-stream",
      "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https: http://localhost:* http://127.0.0.1:*; img-src 'self' data:; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    });
    response.end(body);
  } catch (error) {
    if (error.code === "ENOENT" || error.code === "EISDIR") {
      response.writeHead(404).end("Not found");
      return;
    }
    response.writeHead(500).end("Unable to read the requested file");
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`VitaPulse web is running at http://127.0.0.1:${port}`);
});
