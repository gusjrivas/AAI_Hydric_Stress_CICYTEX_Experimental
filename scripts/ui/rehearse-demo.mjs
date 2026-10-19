// Uso: BASE_URL=http://127.0.0.1:4173 OUT_DIR=demo-rehearsal-out node scripts/ui/rehearse-demo.mjs
// Ensayo TECNICO cronometrado del guion docs/design/demo-guion-defensa.md contra el servidor de fixtures.
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

  // 2. CICYTEX: selectores
  begin();
  await browser.open(`${base}/#defensa-cicytex`);
  check("2a", await waitFor(`!![...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Abrir emisión congelada')&&!b.disabled)`), "catalogo cargado");
  const selects = await evaluate(`[...document.querySelectorAll('select, input[type=date]')].map(s=>({tag:s.tagName,label:s.labels?.[0]?.textContent?.trim()??s.getAttribute('aria-label'),value:s.value}))`);
  check("2b", (await evaluate(`!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Día siguiente')`)) === false, "sin sesion no hay «Dia siguiente»");
  end("2", "#defensa-cicytex: selectores sin sesion", { selects });

  // 3. Abrir emision
  begin();
  await clickText("Abrir emisión congelada");
  check("3a", await waitFor(has("Decisión de la arquitectura")), "decision visible");
  const decision = await evaluate(String.raw`(document.querySelector('main')?.innerText ?? '').match(/DECISIÓN DE LA ARQUITECTURA[\s\S]*?Día siguiente/i)?.[0] ?? ''`);
  check("3b", /SIN ALERTA DE HUMEDAD BAJA/.test(decision) && /acuerdo 0\/3 alertan/.test(decision) && /Ensamble 0\.005/.test(decision), "ensamble 0.005, 0/3 alertan, sin alerta");
  const header = await evaluate(`document.querySelector('h1')?.innerText ?? ''`);
  end("3", "abrir emision congelada", { decision, header });
  await shot(outDir, "3-decision");

  // 4. Trazabilidad
  begin();
  await clickText("Identidad del paquete y de los modelos");
  const trace = await text(".cy-trace");
  check("4a", /Dataset \(SHA-256\)\s*06d662bce07d/.test(trace ?? ""), "SHA-256 del dataset 06d662bc...");
  check("4b", /Versión del modelo: no disponible/.test(trace ?? "") && /Linaje de recalibración: no disponible/.test(trace ?? ""), "version de modelo y linaje: no disponible");
  end("4", "panel de trazabilidad", { trace });
  await shot(outDir, "4-trazabilidad");

  // 5. Dia siguiente
  begin();
  const clock = () => evaluate(String.raw`(document.body.innerText.match(/reloj revelado\s*([0-9-]+)/i) || [])[1] || ''`);
  const c0 = await clock();
  await clickText("Día siguiente");
  await waitFor(`(${String.raw`(document.body.innerText.match(/reloj revelado\s*([0-9-]+)/i) || [])[1] || ''`}) !== ${q(c0)}`);
  const c1 = await clock();
  const summary = await text("[data-testid=moisture-summary]");
  check("5a", c0 === "2023-07-06" && c1 === "2023-07-07", `reloj ${c0} -> ${c1}`);
  end("5", "Dia siguiente", { c0, c1, moistureSummary: summary });

  // 6. Realidad revelada
  begin();
  check("6a", await waitFor(has("Realidad revelada")), "«Realidad revelada»");
  const reveal = await evaluate(String.raw`(document.querySelector('main')?.innerText ?? '').match(/Realidad revelada:[^\n]*|Comparación acumulada revelada[\s\S]*?Solo se usan/g)?.join('\n') ?? ''`);
  check("6b", /resultado VN/.test(reveal) && /Ensamble\t1\t0\t1\t0\t0/.test(reveal), "VN y comparacion acumulada n=1");
  end("6", "realidad revelada y comparacion", { reveal });
  await shot(outDir, "6-realidad-revelada");

  // 7. Feedback
  begin();
  check("7a", (await evaluate(`[...document.querySelectorAll('input[name=cicytex-feedback]')].every(r=>!r.checked)`)), "feedback sin preseleccion");
  await evaluate(`document.querySelectorAll('input[name=cicytex-feedback]')[0].click()`);
  await clickText("Registrar feedback");
  const labels = await evaluate(`[...document.querySelectorAll('input[name=cicytex-feedback]')].map(r=>r.parentElement?.textContent?.trim())`);
  check("7b", await waitFor(has("Feedback registrado")), "feedback confirmado");
  const fb = await evaluate(`document.body.innerText.match(/Feedback registrado[^\\n]*/)?.[0] ?? ''`);
  // reinicio -> borrador limpio
  await clickText("Reiniciar");
  await waitFor(`!document.body.innerText.includes('Feedback registrado')`, 5000);
  end("7", "feedback + reinicio", { labels, fb });

  // 7c. Recuperacion de sesion (plan B de la seccion de fallos)
  begin();
  await clickText("Abrir emisión congelada");
  await waitFor(has("Decisión de la arquitectura"));
  await browser.send("Page.reload");
  check("R1", await waitFor(has("Decisión de la arquitectura"), 15000), "recarga: sesion restaurada");
  await control("mode", { mode: "session-404" });
  await browser.send("Page.reload");
  check("R2", await waitFor(`[...document.querySelectorAll('[role=alert]')].some(e=>e.textContent.includes('No se pudo recuperar la sesión anterior'))`, 15000), "sesion no recuperable: aviso");
  await clickText("Iniciar otra emisión");
  await control("mode", { mode: "normal" });
  end("R", "plan: recarga y sesion no recuperable");

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
