// Uso: BASE_URL=http://127.0.0.1:4173 OUT_DIR=demo-rehearsal-out node scripts/ui/rehearse-demo.mjs
// Ensayo TECNICO cronometrado del recorrido docs/design/presentacion-sin-cicytex.md contra el servidor de fixtures.
// Mide el tiempo de maquina de cada tramo (acciones de UI + espera de que el dato exista); NO mide el tiempo de habla ni
// sustituye el ensayo humano. Escribe rehearsal.json (tiempos, textos observados y chequeos) en OUT_DIR.
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { launchBrowser } from "./lib/cdp.mjs";
import { fetchWithTimeout } from "./lib/timeout.mjs";

const base = (process.env.BASE_URL ?? "http://127.0.0.1:4173").replace(/\/$/, "");
const outDir = process.env.OUT_DIR ?? process.argv[2] ?? join(tmpdir(), "demo-rehearsal");
mkdirSync(outDir, { recursive: true });
const q = JSON.stringify;

const control = async (path, body) =>
  (await fetchWithTimeout(`${base}/__fixture/${path}`, { method: body === undefined ? "GET" : "POST", headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })).json();

const browser = await launchBrowser();
const { evaluate, waitFor, shot } = browser;
const clickText = (text) =>
  evaluate(`(() => { const b=[...document.querySelectorAll('button,a,summary')].find(x=>x.textContent.trim().startsWith(${q(text)})&&!x.disabled&&x.getAttribute('aria-disabled')!=='true'); if(b) b.click(); return !!b; })()`);
const has = (t) => `document.body.innerText.toLowerCase().includes(${q(t.toLowerCase())})`;
const text = (sel) => evaluate(`document.querySelector(${q(sel)})?.innerText?.trim() ?? null`);

const segments = [];
const checks = [];
let t0;
const begin = () => { t0 = performance.now(); };
const end = (id, label, notes = {}) => {
  const ms = Math.round(performance.now() - t0);
  segments.push({ id, label, ms, notes });
  console.log(`${String(ms).padStart(6)} ms  ${id} ${label}`);
};
const check = (id, ok, detail = "") => { checks.push({ id, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"}  ${id} ${detail}`); };

const wall0 = performance.now();
try {
  await control("reset", {});
  await browser.open(`${base}/`);
  await evaluate(`try { sessionStorage.clear(); localStorage.clear(); } catch {}`);

  // 1. Arquitectura
  begin();
  await browser.open(`${base}/#arquitectura`);
  check("1a", await waitFor(`!!document.querySelector('.af-table')`), "mapa de arquitectura cargado");
  await clickText("Laya");
  check("1b", await waitFor(`!!document.querySelector('[aria-label="Ficha de Laya"]')`), "ficha de Laya abierta");
  const laya = await evaluate(`document.querySelector('[aria-label="Ficha de Laya"]')?.innerText ?? ''`);
  check("1c", /Desactivado por defecto/.test(laya), "Laya: Desactivado por defecto");
  const badge = await evaluate(`[...document.querySelectorAll('[class*=mode], [class*=badge]')].map(e=>e.textContent.trim()).filter(Boolean).slice(0,4)`);
  end("1", "#arquitectura + ficha de Laya", { badge, layaSheet: laya.slice(0, 400) });
  await shot(outDir, "1-arquitectura");

  // 8a. Pergamino
  const producer = async (id, route, name, d0) => {
    begin();
    await control("reset", {});
    await browser.open(`${base}/#${route}`);
    check(`${id}a`, await waitFor(`!!document.querySelector('[aria-label="Veredicto del ensamble"]')`), `${name}: veredicto`);
    const verdict = await text(".historical-verdict-label");
    const verdictBlock = await text('[aria-label="Veredicto del ensamble"]');
    const clk = await text(".historical-walkthrough-clock");
    const tr = await text(".historical-trace");
    const sel = await evaluate(`[...document.querySelectorAll('select, input[type=date]')].map(s=>s.value)`);
    end(id, `${name} (${d0})`, { verdict, clk, verdictBlock: verdictBlock?.slice(0, 700), trace: tr?.slice(0, 900), sel });
    begin();
    await clickText("Día siguiente");
    const next = await waitFor(`document.querySelector('.historical-walkthrough-clock')?.textContent.includes('Recorrido avanzado hasta el ${Number(d0.slice(8)) + 1} ')`);
    const rows = await evaluate(`[...document.querySelectorAll('.historical-walkthrough-observations tbody th')].map(e=>e.textContent.trim()).slice(-2)`);
    check(`${id}b`, next, `${name}: reloj avanza un dia; ultimas filas ${rows.join(" / ")}`);
    end(`${id}+`, `${name}: Dia siguiente`, { rows });
    await shot(outDir, `${id}-${route}`);
  };
  await producer("8a", "defensa-pergamino", "Pergamino", "2023-06-13");
  await producer("8b", "defensa-melchor-romero", "Melchor Romero", "2024-10-20");

  // 8c. Laboratorio
  begin();
  await control("reset", {});
  await browser.open(`${base}/#laboratorio-sensores`);
  check("8c-a", await waitFor(`document.querySelector('h1')?.textContent.includes('Laboratorio de sensor simulado')`), "laboratorio");
  await clickText("A — Generar historial");
  check("8c-b", await waitFor(has("Historial sintético cargado: 120 lecturas normales"), 30000), "escenario A");
  end("8c", "laboratorio: escenario A");
  await shot(outDir, "8c-laboratorio-A");
} catch (error) {
  console.error(`ERROR: ${error?.stack ?? error}`);
  checks.push({ id: "crash", ok: false, detail: String(error?.message ?? error) });
} finally {
  await browser.close();
}
const totalMs = Math.round(performance.now() - wall0);
writeFileSync(join(outDir, "rehearsal.json"), JSON.stringify({ base, totalMs, segments, checks }, null, 2));
const fails = checks.filter((c) => !c.ok);
console.log(`\ntotal ${totalMs} ms; ${checks.length - fails.length} PASS, ${fails.length} FAIL`);
process.exit(fails.length ? 1 : 0);
