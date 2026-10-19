// Cliente mínimo de Chrome DevTools Protocol (Node >= 22, WebSocket global, sin dependencias).
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromeArgs, resolveChromePath } from "./chrome.mjs";

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function launchBrowser({ env = process.env, platform = process.platform } = {}) {
  const executable = resolveChromePath({ env, platform, exists: existsSync });
  const profileDir = mkdtempSync(join(tmpdir(), "verify-journeys-"));
  const port = 9333 + Math.floor(Math.random() * 500);
  const chrome = spawn(executable, chromeArgs({ port, profileDir, env }), { stdio: "ignore" });
  let targets;
  for (let i = 0; i < 80 && !targets?.length; i++) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    } catch {
      await sleep(250);
    }
  }
  if (!targets?.length) {
    chrome.kill();
    throw new Error(`Chrome no respondió por CDP (${executable})`);
  }
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) pending.get(message.id)(message);
  };
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const i = ++id;
      pending.set(i, resolve);
      ws.send(JSON.stringify({ id: i, method, params }));
    });
  const evaluate = async (expression) =>
    (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;
  const waitFor = async (expression, ms = 12000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) {
      if (await evaluate(expression)) return true;
      await sleep(150);
    }
    return false;
  };
  const press = async (key, code, vk) => {
    for (const type of ["rawKeyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key, code, windowsVirtualKeyCode: vk });
  };
  const viewport = (width, height) => send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await send("Page.enable");
  await send("Network.enable");
  await viewport(1366, 768);
  return {
    send,
    evaluate,
    waitFor,
    press,
    async open(url) {
      await send("Page.navigate", { url: "about:blank" });
      await send("Page.navigate", { url });
      await waitFor(`document.readyState === 'complete'`, 15000);
    },
    async shot(outDir, name) {
      const height = (await evaluate(`document.documentElement.scrollHeight`)) ?? 768;
      await viewport(1366, Math.min(height, 3000));
      await sleep(200);
      const image = await send("Page.captureScreenshot", { format: "png" });
      writeFileSync(join(outDir, `${name}.png`), Buffer.from(image.result.data, "base64"));
      await viewport(1366, 768);
    },
    async close() {
      try {
        ws.close();
      } catch {}
      chrome.kill();
      await sleep(300);
      try {
        rmSync(profileDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
      } catch {}
    },
  };
}
