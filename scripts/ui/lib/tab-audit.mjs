// Análisis puro de una secuencia de paradas de Tab (pruebas en tab-audit.test.mjs).
// `raw` son las paradas observadas en orden; `left` indica que la secuencia terminó porque el foco salió de la página.
// Un input type=date aporta varias paradas consecutivas (segmentos y selector) del MISMO elemento: cuentan como una.
export function analyzeTabStops(raw, { max, left }) {
  const stops = [];
  let ended = left ? "left" : raw.length >= max ? "max" : "left";
  let trapped = false;
  const seen = new Set();
  for (const item of raw) {
    const last = stops[stops.length - 1];
    if (last && last.id === item.id) continue;
    if (stops.length > 0 && item.id === stops[0].id) {
      ended = "wrapped";
      break;
    }
    if (seen.has(item.id)) trapped = true;
    seen.add(item.id);
    stops.push(item);
  }
  if (ended === "max") trapped = true;
  const withoutIndicator = stops.filter((s) => !s.outline && !s.shadow);
  return { stops, ended, trapped, withoutIndicator };
}
