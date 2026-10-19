import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SensorLabPage } from "./SensorLabPage";

// Pendiente (c) del laboratorio: con el backend apagado (fetch rechazado)
// la persona ve un mensaje claro en español y puede reintentar.
describe("SensorLabPage con backend apagado", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a Spanish role=alert error, never the raw browser text, and lets the person retry", async () => {
    const user = userEvent.setup();
    render(<SensorLabPage />);

    await user.click(screen.getByRole("button", { name: /generar historial de prueba/i }));

    await waitFor(() => expect(screen.getByText("El paso solicitado no pudo completarse")).toBeInTheDocument());
    const labAlert = screen.getAllByRole("alert").find((el) => el.classList.contains("sl-error"))!;
    expect(labAlert).toBeDefined();
    expect(within(labAlert).getByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/failed to fetch/i);

    // No queda bloqueado: se puede iniciar una sesión nueva y volver a intentar el paso A.
    const reset = screen.getByRole("button", { name: /iniciar una sesión nueva/i });
    expect(reset).toBeEnabled();
    await user.click(reset);
    const stepA = screen.getByRole("button", { name: /generar historial de prueba/i });
    expect(stepA).toBeEnabled();
    expect(screen.queryByText("El paso solicitado no pudo completarse")).not.toBeInTheDocument();

    const callsBefore = vi.mocked(fetch).mock.calls.length;
    await user.click(stepA);
    await waitFor(() => expect(screen.getByText("El paso solicitado no pudo completarse")).toBeInTheDocument());
    expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(callsBefore);
    expect(document.body.textContent).not.toMatch(/failed to fetch/i);
  }, 20000);
});
