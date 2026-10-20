import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as cicytexApi from "./features/defense/cicytexApi";

describe("App · ruta #demo-guiada", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    vi.spyOn(cicytexApi, "createCicytexSession").mockReturnValue(new Promise(() => {}));
    vi.spyOn(cicytexApi, "getCicytexProvenance").mockReturnValue(new Promise(() => {}));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    window.location.hash = "";
  });

  it("renders the guided tour at #demo-guiada, separate from #demo", () => {
    window.location.hash = "#demo-guiada";
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: /recorrido guiado/i })).toBeInTheDocument();
    expect(screen.getByText("Paso 1 de 4")).toBeInTheDocument();
    expect(document.title).toMatch(/recorrido guiado/i);
    expect(screen.queryByRole("heading", { name: /^demostración$/i })).not.toBeInTheDocument();
  });

  it("does not render the guided tour on #demo", () => {
    window.location.hash = "#demo";
    render(<App />);
    expect(screen.queryByText("Paso 1 de 4")).not.toBeInTheDocument();
  });

  it("is linked from the technical tools navigation", () => {
    window.location.hash = "#resumen";
    render(<App />);
    expect(screen.getByRole("link", { name: /recorrido guiado/i })).toHaveAttribute("href", "#demo-guiada");
  });
});
