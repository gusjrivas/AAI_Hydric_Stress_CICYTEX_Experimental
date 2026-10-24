import assert from "node:assert/strict";
import { test } from "node:test";
import { classifyUnmatched, createRecorder, EXPECTED_MIN_CHECKS, KNOWN_UNMATCHED, summarize } from "./results.mjs";

test("el recorder clasifica PASS, FAIL e INFO y no guarda datos no deterministas", () => {
  const rec = createRecorder("melchor", () => {});
  rec.check("M1", "carga", true, "ok");
  rec.check("M2", "decisión", false, "faltó");
  rec.info("M3", "observación", "dato");
  assert.deepEqual(
    rec.results.map((r) => [r.id, r.status]),
    [["M1", "PASS"], ["M2", "FAIL"], ["M3", "INFO"]],
  );
  assert.deepEqual(Object.keys(rec.results[0]).sort(), ["evidence", "id", "name", "status"]);
});

test("summarize cuenta por sitio y exige al menos un chequeo por sitio", () => {
  const a = createRecorder("a", () => {});
  a.check("A1", "x", true);
  const b = createRecorder("b", () => {});
  b.check("B1", "y", false);
  b.info("B2", "z", "");
  const s = summarize([a, b]);
  assert.deepEqual([s.pass, s.fail, s.info], [1, 1, 1]);
  assert.equal(s.ok, false);
  assert.deepEqual(s.sites.map((x) => [x.site, x.pass, x.fail, x.info]), [["a", 1, 0, 0], ["b", 0, 1, 1]]);
  const empty = summarize([createRecorder("vacío", () => {})]);
  assert.equal(empty.ok, false);
});

const fill = (site, n) => {
  const rec = createRecorder(site, () => {});
  for (let i = 0; i < n; i++) rec.check(`${site}${i}`, "x", true);
  return rec;
};
const full = (omit = {}) => Object.entries(EXPECTED_MIN_CHECKS).map(([site, n]) => fill(site, n - (omit[site] ?? 0)));

test("EXPECTED_MIN_CHECKS fija los conteos actuales por sitio", () => {
  assert.deepEqual(EXPECTED_MIN_CHECKS, { "melchor-romero": 18, pergamino: 18, "ruta-retirada": 3, laboratorio: 12, "demo-guiada": 20, "arquitectura-laya": 7 });
});

test("summarize falla si un sitio registra menos chequeos que el mínimo y pasa si los tiene", () => {
  assert.equal(summarize(full()).ok, true);
  const short = summarize(full({ pergamino: 1 }));
  assert.equal(short.ok, false);
  assert.deepEqual(short.shortSites, [{ site: "pergamino", total: 17, min: 18 }]);
});

test("classifyUnmatched separa las rutas sin fixture conocidas e inocuas de las demás", () => {
  assert.deepEqual(KNOWN_UNMATCHED, ["GET /api/v2/sectors", "GET /api/v2/sensors"]);
  assert.deepEqual(classifyUnmatched(["GET /api/v2/sensors", "GET /api/v2/sectors"]), { known: ["GET /api/v2/sectors", "GET /api/v2/sensors"], unknown: [] });
  assert.deepEqual(classifyUnmatched(["GET /api/v2/sensors", "POST /api/v2/nuevo"]).unknown, ["POST /api/v2/nuevo"]);
});
