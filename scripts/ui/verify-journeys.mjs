// Uso: BASE_URL=http://localhost:5199 node scripts/ui/verify-journeys.mjs [directorioCapturas]
// Verificación en navegador real (Chrome headless por CDP, Node >= 22, sin dependencias) del recorrido CICYTEX:
// recarga, desconexión y recuperación, permisos de acción y orden de foco por teclado.
// Requiere frontend servido con proxy de /api a un backend con el paquete causal CICYTEX (ver docs/design/f7-verificacion-navegador.md).
// No es una auditoría de accesibilidad automatizada: comprueba lo que se declara en cada chequeo y nada más.
// Limitación: la ruta de Chrome está fija a Windows y usa %TEMP% para el perfil.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

const base = process.env.BASE_URL ?? "http://localhost:5199";
const outDir = process.argv[2] ?? "docs/design/capturas";
mkdirSync(outDir, { recursive: true });
const port = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    `--remote-debugging-port=${port}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${process.env.TEMP}/verify-profile-${port}`,
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
};
const send = (method, params = {}) =>
  new Promise((res) => {
    const i = ++id;
    pending.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
const evaluate = async (expression) =>
  (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

const results = [];
function check(name, ok, evidence) {
  results.push({ name, ok, evidence });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${evidence ? ` — ${evidence}` : ""}`);
}
function observe(name, evidence) {
  results.push({ name, ok: null, evidence });
  console.log(`INFO  ${name} — ${evidence}`);
}

const clickText = (text) =>
  evaluate(
    `(() => { const b=[...document.querySelectorAll('button,a,summary')].find(x=>x.textContent.trim().startsWith(${JSON.stringify(text)})&&!x.disabled); if(b) b.click(); return !!b; })()`,
  );
const waitFor = async (expression, ms = 12000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (await evaluate(expression)) return true;
    await sleep(200);
  }
  return false;
};
const hasText = (text) => `document.body.innerText.toLowerCase().includes(${JSON.stringify(text.toLowerCase())})`;
const CLOCK = String.raw`(document.body.innerText.match(/reloj revelado\s*([0-9-]+)/i) || [])[1] || ''`;
const clock = () => evaluate(CLOCK);
const buttonState = (text) =>
  evaluate(
    `(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim().startsWith(${JSON.stringify(text)})); return b ? (b.disabled ? 'disabled' : 'enabled') : 'absent'; })()`,
  );
async function shot(name) {
  const dims = await evaluate(`({h: document.documentElement.scrollHeight})`);
  await send("Emulation.setDeviceMetricsOverride", { width: 1366, height: Math.min(dims.h, 3000), deviceScaleFactor: 1, mobile: false });
  await sleep(300);
  const s = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${outDir}/${name}.png`, Buffer.from(s.result.data, "base64"));
  await send("Emulation.setDeviceMetricsOverride", { width: 1366, height: 768, deviceScaleFactor: 1, mobile: false });
}
async function press(key, code, vk) {
  for (const type of ["rawKeyDown", "keyUp"]) {
    await send("Input.dispatchKeyEvent", { type, key, code, windowsVirtualKeyCode: vk });
  }
}

await send("Page.enable");
await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1366, height: 768, deviceScaleFactor: 1, mobile: false });

// Preparación: abrir la ruta y esperar el catálogo.
await send("Page.navigate", { url: `${base}/#defensa-cicytex` });
const catalogReady = await waitFor(`!![...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Abrir emisión congelada')&&!b.disabled)`);
check("J0 catálogo cargado en navegador real", catalogReady);

// J1 permisos antes de abrir sesión: nada que avance o registre.
check("J1 sin sesión no hay «Día siguiente» ni feedback", (await buttonState("Día siguiente")) === "absent" && (await buttonState("Registrar feedback")) === "absent");

// J2 abrir emisión y ver la decisión.
await clickText("Abrir emisión congelada");
const opened = await waitFor(hasText("Decisión de la arquitectura"));
check("J2 abrir emisión muestra la decisión", opened);
check("J2b feedback no disponible mientras la realidad está oculta", (await buttonState("Registrar feedback")) === "absent");
await shot("f7-cicytex-sesion-abierta");

// J3 desconexión: «Día siguiente» sin red muestra error y no queda bloqueado.
await send("Network.emulateNetworkConditions", { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
await clickText("Día siguiente");
const errorShown = await waitFor(`!!document.querySelector('[role=alert]')`, 8000);
check("J3 sin red aparece un mensaje de error (role=alert)", errorShown, await evaluate(`document.querySelector('[role=alert]')?.textContent ?? ''`));
check("J3b tras el error el botón vuelve a estar habilitado", (await buttonState("Día siguiente")) === "enabled");
await shot("f7-cicytex-sin-conexion");

// J4 recuperación al volver la red.
await send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
const before = await clock();
await clickText("Día siguiente");
const advanced = await waitFor(`(${CLOCK}) !== ${JSON.stringify(before)}`);
check("J4 al volver la red el reloj avanza y el error desaparece", advanced && !(await evaluate(`!!document.querySelector('[role=alert]')`)), `reloj ${before} → ${await clock()}`);

// J5 revelar realidad habilita feedback (permiso por estado).
for (let i = 0; i < 4 && (await buttonState("Registrar feedback")) === "absent"; i++) {
  const reloj = await clock();
  await clickText("Día siguiente");
  await waitFor(`(${CLOCK}) !== ${JSON.stringify(reloj)}`, 6000);
}
check("J5 con la realidad revelada se habilita el feedback", (await buttonState("Registrar feedback")) !== "absent");
await shot("f7-cicytex-realidad-revelada");

// J6 recarga: qué persiste.
await send("Page.reload");
await sleep(2500);
observe(
  "J6 recarga: ruta y sesión",
  `ruta=${await evaluate("location.hash")}; sesión visible=${await evaluate(hasText("Decisión de la arquitectura"))}; selección de sonda=${await evaluate("document.querySelector('select')?.value")}`,
);
check("J6b tras recargar se conserva la ruta", (await evaluate("location.hash")) === "#defensa-cicytex");

// J7 foco y orden de tab desde la carga.
await send("Page.navigate", { url: `${base}/#defensa-cicytex` });
await waitFor(`!![...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Abrir emisión congelada')&&!b.disabled)`);
await evaluate("document.activeElement && document.activeElement.blur(); window.scrollTo(0,0)");
const stops = [];
for (let i = 0; i < 40; i++) {
  await press("Tab", "Tab", 9);
  const info = await evaluate(`(() => { const e=document.activeElement; if(!e||e===document.body) return null; const cs=getComputedStyle(e); const r=e.getBoundingClientRect(); return {tag:e.tagName.toLowerCase(), text:(e.textContent||e.value||e.getAttribute('aria-label')||'').trim().slice(0,40), outline:cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0, shadow:cs.boxShadow!=='none', visible:r.width>0&&r.height>0}; })()`);
  if (!info) break;
  stops.push(info);
}
const unique = new Set(stops.map((s) => `${s.tag}:${s.text}`));
check("J7 el foco recorre elementos distintos y sale de la página (sin trampa de teclado)", stops.length >= 6 && stops.length < 40 && unique.size === stops.length, `${stops.length} paradas, ${unique.size} distintas`);
const noIndicator = stops.filter((s) => !s.outline && !s.shadow);
check("J7b todo elemento enfocado muestra indicador de foco", noIndicator.length === 0, noIndicator.map((s) => `${s.tag}:${s.text}`).join(" | "));
const idxOpen = stops.findIndex((s) => s.text.startsWith("Abrir emisión congelada"));
const idxSensor = stops.findIndex((s) => s.tag === "select");
check("J7c los controles se alcanzan en orden lógico (selectores antes de «Abrir»)", idxSensor >= 0 && idxOpen > idxSensor, `select@${idxSensor}, abrir@${idxOpen}`);
writeFileSync(`${outDir}/f7-orden-de-foco.json`, JSON.stringify(stops, null, 2));

ws.close();
chrome.kill();
const failed = results.filter((r) => r.ok === false);
writeFileSync(`${outDir}/f7-verificacion-navegador.json`, JSON.stringify(results, null, 2));
console.log(`\n${results.filter((r) => r.ok === true).length} PASS, ${failed.length} FAIL, ${results.filter((r) => r.ok === null).length} INFO`);
process.exit(failed.length ? 1 : 0);
