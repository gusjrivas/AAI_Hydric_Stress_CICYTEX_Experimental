// Selección portable de Chrome y argumentos de arranque (helpers puros, con pruebas en chrome.test.mjs).
const WINDOWS = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
];
const LINUX = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser"];
const MAC = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"];

export function resolveChromePath({ env, platform, exists }) {
  if (env.CHROME_PATH) {
    if (!exists(env.CHROME_PATH)) throw new Error(`CHROME_PATH no existe: ${env.CHROME_PATH}`);
    return env.CHROME_PATH;
  }
  const candidates = platform === "win32" ? WINDOWS : platform === "darwin" ? MAC : LINUX;
  const found = candidates.find((path) => exists(path));
  if (!found) throw new Error(`No se encontró Chrome en ${candidates.join(", ")}; definí CHROME_PATH.`);
  return found;
}

export function chromeArgs({ port, profileDir, env }) {
  const args = [
    `--remote-debugging-port=${port}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${profileDir}`,
  ];
  if (env.CI === "true" || env.CI === "1") args.push("--no-sandbox", "--disable-dev-shm-usage");
  args.push("about:blank");
  return args;
}
