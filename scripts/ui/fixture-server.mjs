// Uso: node scripts/ui/fixture-server.mjs   (PORT=4173, STATIC_DIR=frontend/dist/e2e, FIXTURES_DIR=frontend/e2e/fixtures)
// Sirve el build del frontend y, en el mismo origen, las respuestas grabadas del backend (sin dependencias, sin red externa).
// Control para las pruebas: POST /__fixture/mode {"mode":"normal|disconnected|session-404"}, POST /__fixture/reset,
// GET /__fixture/state. «disconnected» destruye el socket de cualquier ruta de API (el navegador ve un fallo de red).
import { createServer } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { createFixtureHandler } from "./lib/fixture-handler.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
const repo = resolve(here, "..", "..");
const port = Number(process.env.PORT ?? 4173);
const staticDir = resolve(process.env.STATIC_DIR ?? join(repo, "frontend", "dist", "e2e"));
const fixturesDir = resolve(process.env.FIXTURES_DIR ?? join(repo, "frontend", "e2e", "fixtures"));

const handler = createFixtureHandler({
  load(relative) {
    const file = resolve(fixturesDir, relative);
    if (!file.startsWith(fixturesDir + sep) || !existsSync(file)) return undefined;
    return JSON.parse(readFileSync(file, "utf8"));
  },
});

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2" };
const API_PREFIXES = ["/api/", "/sensors/", "/quality/", "/forecast/", "/feedback/", "/models/", "/recalibrate/", "/lineage/"];

const readBody = (req) =>
  new Promise((done) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      try {
        done(text ? JSON.parse(text) : undefined);
      } catch {
        done(undefined);
      }
    });
  });

function sendJson(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, { "content-type": "application/json", "cache-control": "no-store", "content-length": Buffer.byteLength(data) });
  res.end(data);
}

function sendStatic(res, pathname) {
  let file = normalize(join(staticDir, pathname));
  if (!file.startsWith(staticDir)) return sendJson(res, 403, { detail: "fuera de STATIC_DIR" });
  if (!existsSync(file) || statSync(file).isDirectory()) file = join(staticDir, "index.html");
  if (!existsSync(file)) return sendJson(res, 404, { detail: "STATIC_DIR sin build: ejecutá npm run build" });
  res.writeHead(200, { "content-type": TYPES[extname(file)] ?? "application/octet-stream", "cache-control": "no-store" });
  res.end(readFileSync(file));
}

createServer(async (req, res) => {
  const url = req.url ?? "/";
  const pathname = url.split("?")[0];
  if (pathname.startsWith("/__fixture/")) {
    if (pathname === "/__fixture/mode" && req.method === "POST") {
      try {
        handler.setMode((await readBody(req))?.mode);
      } catch (error) {
        return sendJson(res, 400, { detail: error.message });
      }
    } else if (pathname === "/__fixture/reset" && req.method === "POST") {
      handler.reset();
    } else if (pathname !== "/__fixture/state") {
      return sendJson(res, 404, { detail: "control desconocido" });
    }
    return sendJson(res, 200, { mode: handler.mode, unmatched: handler.unmatched });
  }
  if (API_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    const body = req.method === "POST" ? await readBody(req) : undefined;
    const result = handler.handle({ method: req.method ?? "GET", path: url, body });
    if (result.drop) return req.socket.destroy();
    return sendJson(res, result.status, result.body);
  }
  sendStatic(res, pathname);
}).listen(port, "127.0.0.1", () => console.log(`fixture-server en http://127.0.0.1:${port} (static=${staticDir}, fixtures=${fixturesDir})`));
