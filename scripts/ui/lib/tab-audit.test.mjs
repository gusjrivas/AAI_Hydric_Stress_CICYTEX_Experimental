import assert from "node:assert/strict";
import { test } from "node:test";
import { analyzeTabStops } from "./tab-audit.mjs";

const stop = (id, extra = {}) => ({ id, tag: "a", text: `e${id}`, outline: true, shadow: false, ...extra });

test("segmentos consecutivos de un mismo elemento (input date) cuentan como una parada", () => {
  const r = analyzeTabStops([stop(1), stop(2), stop(2), stop(2), stop(3)], { max: 50, left: true });
  assert.deepEqual(r.stops.map((s) => s.id), [1, 2, 3]);
  assert.equal(r.trapped, false);
  assert.equal(r.ended, "left");
});

test("volver al primer elemento es una vuelta completa, no una trampa", () => {
  const r = analyzeTabStops([stop(1), stop(2), stop(3), stop(1), stop(2)], { max: 50, left: false });
  assert.deepEqual(r.stops.map((s) => s.id), [1, 2, 3]);
  assert.equal(r.ended, "wrapped");
  assert.equal(r.trapped, false);
});

test("repetir un elemento que no es el primero es una trampa", () => {
  const r = analyzeTabStops([stop(1), stop(2), stop(3), stop(2), stop(3), stop(2)], { max: 50, left: false });
  assert.equal(r.trapped, true);
});

test("no terminar dentro del máximo es una trampa", () => {
  const raw = Array.from({ length: 10 }, (_, i) => stop(i + 1));
  const r = analyzeTabStops(raw, { max: 10, left: false });
  assert.equal(r.ended, "max");
  assert.equal(r.trapped, true);
});

test("el indicador de foco se juzga en la primera parada del elemento", () => {
  const r = analyzeTabStops([stop(1), stop(2), stop(2, { outline: false })], { max: 50, left: true });
  assert.deepEqual(r.withoutIndicator, []);
  const bad = analyzeTabStops([stop(1, { outline: false }), stop(2)], { max: 50, left: true });
  assert.equal(bad.withoutIndicator.length, 1);
});
