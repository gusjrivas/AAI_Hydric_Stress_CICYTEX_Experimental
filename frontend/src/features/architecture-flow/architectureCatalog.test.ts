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
});
