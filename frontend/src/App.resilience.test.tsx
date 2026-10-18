import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { ROUTES } from "./features/navigation/useHashRoute";

// F7: con el backend desconectado ninguna vista debe romperse ni dejar la
// pantalla sin contenido principal, y el modo de lectura debe seguir visible.
describe("App con backend desconectado", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    window.location.hash = "";
  });

  it.each(ROUTES)("renders #%s with a main region and a visible mode badge", async (route) => {
    window.location.hash = `#${route}`;
    render(<App />);

    expect(await screen.findByRole("main")).toBeInTheDocument();
    expect(screen.getAllByRole("note").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { level: 1 }).length).toBeGreaterThan(0);
  });

  it("keeps Laya disabled and no live telemetry on the architecture view", async () => {
    window.location.hash = "#arquitectura";
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Laya" }));
    const sheet = screen.getByRole("region", { name: "Ficha de Laya" });
    expect(sheet).toHaveTextContent("Desactivado por defecto");
    expect(screen.getAllByText(/no es monitoreo en vivo/i).length).toBeGreaterThan(0);
  });

  it("lets keyboard users open a component sheet with Tab and Enter", async () => {
    window.location.hash = "#arquitectura";
    render(<App />);
    const button = await screen.findByRole("button", { name: "Datos IoT" });

    button.focus();
    await userEvent.keyboard("{Enter}");

    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("region", { name: "Ficha de Datos IoT" })).toBeInTheDocument();
  });
});
