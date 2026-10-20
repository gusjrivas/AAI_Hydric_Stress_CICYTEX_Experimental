import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync("src/features/guided-demo/GuidedDemoPage.css", "utf-8");

function minHeightOf(selector: string): number {
  const rule = css.split("}").find((block) => block.split("{")[0].split(",").some((s) => s.trim() === selector));
  const match = rule?.match(/min-height:\s*(\d+)px/);
  return match ? Number(match[1]) : 0;
}

describe("GuidedDemoPage · objetivos táctiles", () => {
  it.each([".gd-btn", ".gd-details summary"])("%s mide al menos 44px", (selector) => {
    expect(minHeightOf(selector)).toBeGreaterThanOrEqual(44);
  });
});
