// Uso: node scripts/ui/capture-view.mjs <url> <prefijoSalida> [textoDeClic ...]
// Controla Chrome por CDP (Node >= 22, sin dependencias). Captura escritorio (1366x768) y estrecho (360x740).
// Requiere un frontend servido (p. ej. `npm run dev` con proxy de /api al backend) y Chrome instalado.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const [url, prefix, ...clicks] = process.argv.slice(2);
const port = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    `--remote-debugging-port=${port}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${process.env.TEMP}/shot-profile-${port}`,
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

async function shoot(name, width, height) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 600 });
  await send("Page.navigate", { url });
  await sleep(2500);
  for (const text of clicks) {
    await evaluate(
      `(() => { const b=[...document.querySelectorAll('button,a')].find(x=>x.textContent.trim().startsWith(${JSON.stringify(text)})&&!x.disabled); if(b) b.click(); return !!b; })()`,
    );
    await sleep(1800);
  }
  if (process.env.OVERFLOW) {
    console.log(name, await evaluate(`JSON.stringify([...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>window.innerWidth+1).slice(0,8).map(e=>e.tagName+'.'+e.className+' '+Math.round(e.getBoundingClientRect().right)))`));
  }
  const dims = await evaluate(`({h: document.documentElement.scrollHeight, w: document.documentElement.scrollWidth})`);
  await send("Emulation.setDeviceMetricsOverride", {
    width,
    height: Math.min(dims.h, 4000),
    deviceScaleFactor: 1,
    mobile: width < 600,
  });
  await sleep(500);
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${prefix}-${name}.png`, Buffer.from(shot.result.data, "base64"));
  console.log(name, "scrollWidth", dims.w, "viewport", width, "height", dims.h);
}

await send("Page.enable");
await shoot("desktop", 1366, 768);
await shoot("narrow", 360, 740);
ws.close();
chrome.kill();
process.exit(0);
