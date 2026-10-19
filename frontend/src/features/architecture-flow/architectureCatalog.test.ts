import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ARCHITECTURE_NODES } from "./architectureCatalog";
import { ROUTES } from "../navigation/useHashRoute";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");

describe("architecture catalog", () => {
  it("keeps the seven original stages in order", () => {
    expect(ARCHITECTURE_NODES.filter((n) => n.kind === "stage").map((n) => n.id)).toEqual([
      "iot", "calidad", "features", "prediccion", "alertas", "feedback", "recalibracion",
    ]);
  });

  it("points every evidence reference to an existing repository path", () => {
    for (const node of ARCHITECTURE_NODES) {
      expect(node.evidence.length, node.id).toBeGreaterThan(0);
      for (const path of node.evidence) {
        expect(existsSync(resolve(REPO_ROOT, path)), `${node.id}: ${path}`).toBe(true);
      }
    }
  });

  it("links only to existing routes", () => {
    for (const node of ARCHITECTURE_NODES) {
      expect(ROUTES as readonly string[], node.id).toContain(node.anchor);
    }
  });

  it("declares responsibility, input, output, boundary and limits for every node", () => {
    for (const node of ARCHITECTURE_NODES) {
      for (const field of ["responsibility", "input", "output", "boundary", "limits"] as const) {
        expect(node[field].trim().length, `${node.id}.${field}`).toBeGreaterThan(0);
      }
    }
  });

  it("presents Laya as an advisory adapter that is disabled, never as an active stage", () => {
    const laya = ARCHITECTURE_NODES.find((n) => n.id === "laya");
    expect(laya?.kind).toBe("adapter");
    expect(laya?.status).toBe("desactivado");
    expect(laya?.limits).toMatch(/sin sugerencias reales en esta configuración/i);
  });
  it("keeps every Laya claim optional, disabled by default and never a scientific validation", () => {
    const laya = ARCHITECTURE_NODES.find((n) => n.id === "laya")!;
    const text = [laya.label, laya.responsibility, laya.input, laya.output, laya.boundary, laya.limits].join(" ");
    expect(text).toMatch(/opcional/i);
    expect(text).toMatch(/deshabilitado por defecto/i);
    expect(text).toMatch(/sin efecto autom[aá]tico/i);
    expect(text).toMatch(/utilidad no est[aá] evaluada/i);
    // Ninguna afirmación de validación científica, corpus real, calibración ni resultados.
    expect(text).not.toMatch(/validad[oa]|validaci[oó]n cient|corpus real|calibrad[oa]|calibraci[oó]n|accuracy|exactitud|resultados? (reales|obtenidos)|mejora/i);
    expect(laya.status).toBe("desactivado");
  });
});
