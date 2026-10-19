import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// Pendiente (a): a <=600px los controles del laboratorio miden >=44px.
// jsdom/css:false no calcula layout, así que se fija la regla en el CSS.
const css = readFileSync("src/features/lab/SensorLabPage.css", "utf-8");
const media = css.match(/@media \(max-width: 600px\)\s*\{([\s\S]*?)\n\}/);

describe("laboratorio: objetivos táctiles a <=600px", () => {
  it("has a max-width: 600px block", () => {
    expect(media).not.toBeNull();
  });

  it.each([
    ["selects de filtros", /\.sensor-lab[^{]*select[^{]*\{[^}]*min-height:\s*44px/],
    ["summary de detalles", /\.sensor-lab[^{]*summary[^{]*\{[^}]*min-height:\s*44px/],
    ["enlace Ir al Laboratorio", /\.sensor-lab[^{]*\.no-readings-hint a[^{]*\{[^}]*min-height:\s*44px/],
  ])("guarantees 44px for %s", (_name, pattern) => {
    expect(media?.[1]).toMatch(pattern);
  });
});
