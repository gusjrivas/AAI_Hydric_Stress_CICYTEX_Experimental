import assert from "node:assert/strict";
import { test } from "node:test";
import { createRecorder, summarize } from "./results.mjs";

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
