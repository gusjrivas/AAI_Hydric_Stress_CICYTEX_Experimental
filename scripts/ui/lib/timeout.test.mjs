import assert from "node:assert/strict";
import { test } from "node:test";
import { timeoutMs, withTimeout } from "./timeout.mjs";

test("withTimeout rechaza con un mensaje diagnóstico si la promesa no resuelve", async () => {
  await assert.rejects(withTimeout(new Promise(() => {}), 20, "CDP Page.navigate"), /20 ms.*CDP Page\.navigate/);
});

test("withTimeout devuelve el valor si resuelve a tiempo", async () => {
  assert.equal(await withTimeout(Promise.resolve(7), 200, "x"), 7);
});

test("timeoutMs lee CDP_TIMEOUT_MS y usa el valor por defecto si es inválido", () => {
  assert.equal(timeoutMs(30000, { CDP_TIMEOUT_MS: "500" }), 500);
  assert.equal(timeoutMs(30000, { CDP_TIMEOUT_MS: "abc" }), 30000);
  assert.equal(timeoutMs(10000, {}), 10000);
});
