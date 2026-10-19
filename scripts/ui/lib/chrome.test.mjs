import assert from "node:assert/strict";
import { test } from "node:test";
import { chromeArgs, resolveChromePath } from "./chrome.mjs";

const existing = (...paths) => (p) => paths.includes(p);

test("CHROME_PATH tiene prioridad y debe existir", () => {
  const env = { CHROME_PATH: "/opt/chrome/chrome" };
  assert.equal(resolveChromePath({ env, platform: "linux", exists: existing("/opt/chrome/chrome") }), "/opt/chrome/chrome");
  assert.throws(() => resolveChromePath({ env, platform: "linux", exists: existing() }), /CHROME_PATH/);
});

test("Windows usa las rutas habituales de Chrome", () => {
  const p = "C:/Program Files/Google/Chrome/Application/chrome.exe";
  assert.equal(resolveChromePath({ env: {}, platform: "win32", exists: existing(p) }), p);
});

test("Linux prueba google-chrome antes que chromium", () => {
  const found = resolveChromePath({ env: {}, platform: "linux", exists: existing("/usr/bin/chromium", "/usr/bin/google-chrome") });
  assert.equal(found, "/usr/bin/google-chrome");
  assert.equal(resolveChromePath({ env: {}, platform: "linux", exists: existing("/usr/bin/chromium") }), "/usr/bin/chromium");
});

test("sin Chrome falla con un mensaje accionable", () => {
  assert.throws(() => resolveChromePath({ env: {}, platform: "linux", exists: existing() }), /CHROME_PATH/);
});

test("chromeArgs agrega --no-sandbox solo en CI", () => {
  const base = { port: 9400, profileDir: "/tmp/p" };
  assert.ok(!chromeArgs({ ...base, env: {} }).includes("--no-sandbox"));
  assert.ok(chromeArgs({ ...base, env: { CI: "true" } }).includes("--no-sandbox"));
  const args = chromeArgs({ ...base, env: {} });
  assert.ok(args.includes("--remote-debugging-port=9400"));
  assert.ok(args.includes("--user-data-dir=/tmp/p"));
});
