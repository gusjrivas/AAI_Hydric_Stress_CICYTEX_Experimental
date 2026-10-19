// Captura y mide el recorrido completo del laboratorio de sensor simulado (pasos A-D) en 360 px y 1366 px.
//
// Uso:
//   LAB_URL=http://localhost:5199/#laboratorio-sensores OUT_DIR=./salida node scripts/ui/capture-lab.mjs
//
// Variables de entorno:
//   LAB_URL      URL del laboratorio (por defecto http://localhost:5199/#laboratorio-sensores).
//   OUT_DIR      directorio de salida de los PNG (por defecto ./lab-captures).
//   CHROME_PATH  ejecutable de Chrome/Chromium (por defecto, rutas habituales de Windows/macOS/Linux).
//   PROFILE_DIR  perfil temporal de Chrome (por defecto <tmp>/lab-capture-profile-<puerto>).
//   VIEWPORTS    lista "ancho x alto" separada por comas (por defecto 360x740,1366x768).
//   ERROR_MODE   "post" para hacer fallar toda peticion POST a la API y capturar el estado de error
//                (solo ejecuta el paso A en cada viewport); vacio para el recorrido completo.
//   STEP_TIMEOUT_MS  espera maxima por paso (por defecto 90000).
//
// Requisitos: Node >= 22 (WebSocket global), Chrome instalado, frontend (vite) y backend FastAPI en marcha.
// El backend DEBE apuntar a una copia desechable de los datos: el recorrido escribe lecturas y revisiones.
//
// Que hace: hace clic en cada paso y ESPERA a que el siguiente boton este habilitado (sin pausas fijas);
// captura la pagina completa (captureBeyondViewport, en tramos si supera 16000 px) en cada paso y mide
// desbordes reales (getBoundingClientRect().right > innerWidth) y el tamano tactil de los controles.
//
// Limitaciones: la captura redimensiona el viewport a la altura de la pagina (los elementos fijos aparecen al pie);
//  la medicion tactil usa el umbral de 44 px del proyecto (WCAG 2.2 AA exige 24 px);
// no sustituye una prueba en dispositivo real; los tramos de pagina muy larga se guardan como -pN.png;
// el emulador de movil de Chrome no reproduce tipografia ni barras del sistema de un telefono real.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const URL_LAB = process.env.LAB_URL ?? "http://localhost:5199/#laboratorio-sensores";
const OUT = process.env.OUT_DIR ?? "./lab-captures";
const ERROR_MODE = process.env.ERROR_MODE ?? "";
const STEP_TIMEOUT = Number(process.env.STEP_TIMEOUT_MS ?? 90000);
const MAX_TILE = 16000;
const viewports = (process.env.VIEWPORTS ?? "360x740,1366x768").split(",").map((v) => v.split("x").map(Number));
mkdirSync(OUT, { recursive: true });

const candidates = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const chromePath = candidates.find((p) => existsSync(p));
if (!chromePath) throw new Error("No se encontro Chrome; defina CHROME_PATH.");

const port = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn(
  chromePath,
  [
    `--remote-debugging-port=${port}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${process.env.PROFILE_DIR ?? join(tmpdir(), `lab-capture-profile-${port}`)}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    if (targets.length) break;
  } catch {}
  await sleep(250);
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) pending.get(m.id)(m);
  else if (m.method === "Fetch.requestPaused") {
    const req = m.params.request;
    const fail = ERROR_MODE === "post" && req.method === "POST";
    send(fail ? "Fetch.failRequest" : "Fetch.continueRequest", fail
      ? { requestId: m.params.requestId, errorReason: "ConnectionFailed" }
      : { requestId: m.params.requestId });
  }
};
const send = (method, params = {}) =>
  new Promise((res) => {
    const i = ++id;
    pending.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
const evaluate = async (expression) =>
  (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

async function waitFor(label, expression) {
  const t0 = Date.now();
  while (Date.now() - t0 < STEP_TIMEOUT) {
    if (await evaluate(expression)) return Date.now() - t0;
    await sleep(150);
  }
  throw new Error(`Tiempo agotado esperando: ${label}`);
}

// Boton de un paso (A-D) por su letra inicial; "Generando…/Enviando…/Simulando…" cuentan como ocupado.
const stepBtn = (letter) =>
  `[...document.querySelectorAll('.sl-steps button')].find(b=>b.textContent.trim().startsWith(${JSON.stringify(letter)}+' —'))`;
const stepEnabled = (letter) => `(() => { const b = ${stepBtn(letter)}; return !!b && !b.disabled; })()`;
const clickStep = (letter) => evaluate(`(() => { const b = ${stepBtn(letter)}; if (b && !b.disabled) { b.click(); return true; } return false; })()`);

const overflowProbe = `(() => {
  const W = window.innerWidth;
  const desc = (e) => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/).join('.') : '');
  const clipped = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o !== 'visible' && p.getBoundingClientRect().right <= W + 1) return true; } return false; };
  const out = [];
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right > W + 1 || r.left < -1) out.push({ el: desc(e), left: Math.round(r.left), right: Math.round(r.right), clippedByScrollParent: clipped(e) });
  }
  return { innerWidth: W, scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight,
    real: out.filter((o) => !o.clippedByScrollParent).slice(0, 12), clippedCount: out.filter((o) => o.clippedByScrollParent).length };
})()`;

const touchProbe = `(() => [...document.querySelectorAll('button, a[href], summary, input:not([type=hidden]), select, textarea, [role=button]')]
  .map((e) => ({ e, r: e.getBoundingClientRect() }))
  .filter(({ r }) => r.width > 0 && r.height > 0 && (r.height < 44 || r.width < 44))
  .slice(0, 20)
  .map(({ e, r }) => (e.tagName.toLowerCase() + (e.type ? '[' + e.type + ']' : '') + ' "' + (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 40) + '" ' + Math.round(r.width) + 'x' + Math.round(r.height))))()`;

async function fullPage(name, width, height) {
  const dims = await evaluate(`({h: document.documentElement.scrollHeight})`);
  const files = [];
  // Viewport tan alto como la pagina: los elementos fijos (barra inferior en movil) quedan al pie y no tapan contenido.
  await send("Emulation.setDeviceMetricsOverride", { width, height: Math.min(dims.h, MAX_TILE), deviceScaleFactor: 1, mobile: width < 600 });
  await sleep(300);
  for (let y = 0, n = 1; y < dims.h; y += MAX_TILE, n++) {
    const h = Math.min(MAX_TILE, dims.h - y);
    const shot = await send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: { x: 0, y, width, height: h, scale: 1 },
    });
    const file = join(OUT, dims.h > MAX_TILE ? `${name}-p${n}.png` : `${name}.png`);
    writeFileSync(file, Buffer.from(shot.result.data, "base64"));
    files.push(file);
  }
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 600 });
  return { files, height: dims.h };
}

async function measure(tag, width, height) {
  const o = await evaluate(`JSON.stringify(${overflowProbe})`);
  const t = width < 600 ? await evaluate(`JSON.stringify(${touchProbe})`) : "[]";
  const shots = await fullPage(`lab-${width}-${tag}`, width, height);
  console.log(`[${width}] ${tag}: alto ${shots.height}px; desborde ${o}; controles <44px ${t}; archivos ${shots.files.length}`);
}

await send("Page.enable");
if (ERROR_MODE === "post") await send("Fetch.enable", { patterns: [{ urlPattern: "*", requestStage: "Request" }] });
for (const [width, height] of viewports) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 600 });
  await send("Page.navigate", { url: "about:blank" });
  await send("Page.navigate", { url: URL_LAB });
  await waitFor("paso A habilitado", stepEnabled("A"));
  if (!ERROR_MODE) await measure("inicio", width, height);
  for (const [cur, next] of [["A", "B"], ["B", "C"], ["C", "D"], ["D", null]]) {
    await clickStep(cur);
    if (ERROR_MODE === "post") {
      const ms = await waitFor("mensaje de error", `!!document.querySelector('[role=alert]')`);
      console.log(`[${width}] error visible tras ${ms} ms`);
      await sleep(500);
      await measure("error", width, height);
      break;
    }
    const ms = next
      ? await waitFor(`paso ${next} habilitado`, stepEnabled(next))
      : await waitFor("recorrido terminado", `(() => { const b = ${stepBtn("D")}; return !!b && b.disabled && /termin/i.test(document.querySelector('.sl-disabled-note')?.textContent ?? ''); })()`);
    console.log(`[${width}] paso ${cur} listo en ${ms} ms`);
    await sleep(400); // asentamiento visual de transiciones tras la condicion de estado
    await measure(next ? `paso-${next.toLowerCase()}` : "final", width, height);
  }
}
ws.close();
chrome.kill();
process.exit(0);
