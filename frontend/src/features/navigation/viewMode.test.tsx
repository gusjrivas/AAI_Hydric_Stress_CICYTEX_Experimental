import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ModeBadge } from "./ModeBadge";
import { modeForView } from "./viewMode";

describe("modeForView", () => {
  it.each([
    ["productor", "operacion"],
    ["resumen", "operacion"],
    ["prediccion", "operacion"],
    ["calidad", "operacion"],
    ["linaje", "operacion"],
    ["demo", "laboratorio"],
    ["laboratorio-sensores", "laboratorio"],
    ["defensa-pergamino", "replay"],
    ["defensa-melchor-romero", "replay"],
    ["reproduccion-historica", "replay"],
    ["evidencia-resultados", "diseno"],
    ["evidencia", "diseno"],
    ["arquitectura", "diseno"],
  ] as const)("classifies %s as %s", (view, mode) => {
    expect(modeForView(view)).toBe(mode);
  });
});

describe("modeForView with simulated sensors", () => {
  it("never labels a simulated active sensor as operation", () => {
    expect(modeForView("resumen", { simulatedSensor: true })).toBe("laboratorio");
    expect(modeForView("productor", { simulatedSensor: false })).toBe("operacion");
  });
  it("does not relabel replay or design views", () => {
    expect(modeForView("defensa-pergamino", { simulatedSensor: true })).toBe("replay");
    expect(modeForView("arquitectura", { simulatedSensor: true })).toBe("diseno");
  });
});

describe("ModeBadge", () => {
  it.each([
    ["operacion", /operación/i],
    ["replay", /replay histórico/i],
    ["laboratorio", /laboratorio sintético/i],
    ["diseno", /documentación de diseño/i],
  ] as const)("shows visible text for %s, not only color", (mode, text) => {
    render(<ModeBadge mode={mode} />);
    expect(screen.getByRole("note")).toHaveTextContent(text);
  });
});
