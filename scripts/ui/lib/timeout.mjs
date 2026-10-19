// Timeouts con error diagnóstico para comandos CDP y fetch de control (evita cuelgues silenciosos en CI).
export const timeoutMs = (fallback, env = process.env) => {
  const value = Number(env.CDP_TIMEOUT_MS);
  return Number.isFinite(value) && value > 0 ? value : fallback;
};

export function withTimeout(promise, ms, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timeout tras ${ms} ms: ${label}`)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

export async function fetchWithTimeout(url, options = {}, ms = timeoutMs(10000)) {
  const controller = new AbortController();
  const label = `fetch ${options.method ?? "GET"} ${url}`;
  try {
    return await withTimeout(fetch(url, { ...options, signal: controller.signal }), ms, label);
  } catch (error) {
    controller.abort();
    throw error;
  }
}
