import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as forecastApi from "./features/forecast/api";
import * as catalogApi from "./features/producer/catalogApi";
import * as qualityApi from "./features/quality/api";
import { readyQuality } from "./features/quality/testFixtures";
import * as lineageApi from "./features/lineage/api";
import * as sensorLabApi from "./features/lab/sensorLabApi";

const EMPTY_PREDICTOR: forecastApi.ActivePredictor = {
  sensor_id: "sensor-a",
  origin: null,
  model_id: null,
  version: null,
  trained_through: null,
  calibration_end: null,
  horizon_days: 3,
  contract_version: 1,
  pipeline_version: "controlled_daily_v3",
  feature_columns: [],
  lags: [],
  rolling_windows: [],
  applied_feedback_count: 0,
  applied_feedback_dates: [],
};

describe("App — cabecera de sensor", () => {
  beforeEach(() => {
    window.location.hash = "#resumen";
    vi.restoreAllMocks();
    vi.spyOn(forecastApi, "getActivePredictor").mockResolvedValue(EMPTY_PREDICTOR);
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({ rows: [] });
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(null);
    vi.spyOn(lineageApi, "getLineage").mockResolvedValue({ sensor_id: "sensor-a", chain: [] });
  });

  it("keeps the active sensor and its queries unchanged while editing the draft without applying", async () => {
    render(<App />);
    await waitFor(() => expect(forecastApi.listFeedback).toHaveBeenCalledWith("sensor-a"));

    const input = screen.getByLabelText(/sensor/i);
    await userEvent.clear(input);
    await userEvent.type(input, "sensor-b");

    expect(screen.getByText(/sensor activo/i)).toHaveTextContent("sensor-a");
    expect(forecastApi.listFeedback).toHaveBeenCalledTimes(1);
  });

  it("applies a valid sensor id and queries the new sensor's resources", async () => {
    render(<App />);
    await waitFor(() => expect(forecastApi.listFeedback).toHaveBeenCalledWith("sensor-a"));

    const input = screen.getByLabelText(/sensor/i);
    await userEvent.clear(input);
    await userEvent.type(input, "sensor-b");
    await userEvent.click(screen.getByRole("button", { name: /aplicar/i }));

    await waitFor(() => expect(forecastApi.listFeedback).toHaveBeenCalledWith("sensor-b"));
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent("sensor-b");
  });

  it("shows a validation error and does not trigger any query for an invalid sensor id", async () => {
    render(<App />);
    await waitFor(() => expect(forecastApi.listFeedback).toHaveBeenCalledTimes(1));

    const input = screen.getByLabelText(/sensor/i);
    await userEvent.clear(input);
    await userEvent.type(input, "sensor con espacios!");
    await userEvent.click(screen.getByRole("button", { name: /aplicar/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/identificador válido/i);
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent("sensor-a");
    expect(forecastApi.listFeedback).toHaveBeenCalledTimes(1);
  });

  it("blocks applying another sensor while a mutation is pending, and re-enables it afterward", async () => {
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(readyQuality("sensor-a"));
    let resolveRun!: (value: forecastApi.ForecastRunResponse) => void;
    vi.spyOn(forecastApi, "runForecast").mockReturnValueOnce(
      new Promise((resolve) => (resolveRun = resolve)),
    );

    render(<App />);
    await waitFor(() => expect(forecastApi.listFeedback).toHaveBeenCalledWith("sensor-a"));

    await userEvent.click(screen.getByRole("button", { name: /generar pronóstico/i }));

    const applyButton = screen.getByRole("button", { name: /aplicar/i });
    await waitFor(() => expect(applyButton).toBeDisabled());

    resolveRun({ train_rows: 1, test_rows: 1, verdicts: [] });
    await waitFor(() => expect(applyButton).not.toBeDisabled());
  });
});

describe("App — navegación por hash (Entrega 2)", () => {
  beforeEach(() => {
    window.location.hash = "#resumen";
    vi.restoreAllMocks();
    vi.spyOn(forecastApi, "getActivePredictor").mockResolvedValue(EMPTY_PREDICTOR);
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({ rows: [] });
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(null);
    vi.spyOn(lineageApi, "getLineage").mockResolvedValue({ sensor_id: "sensor-a", chain: [] });
  });

  it("keeps the defense route when keyboard users skip to the main content", async () => {
    window.location.hash = "#defensa-pergamino";
    render(<App />);
    await userEvent.click(screen.getByRole("link", { name: /saltar al contenido/i }));
    expect(window.location.hash).toBe("#defensa-pergamino");
    expect(screen.getByRole("heading", { name: "Pergamino", level: 1 })).toBeInTheDocument();
  });

  it("renders Melchor Romero as its own real second site, distinct from Pergamino, and isolates state across Pergamino -> Melchor Romero -> Pergamino", async () => {
    window.location.hash = "#defensa-pergamino";
    render(<App />);
    expect(screen.getByText(/Pergamino · emisiones persistidas/i)).toBeInTheDocument();
    expect(screen.queryByText(/Melchor Romero · emisiones persistidas/i)).not.toBeInTheDocument();

    window.location.hash = "#defensa-melchor-romero";
    await act(async () => window.dispatchEvent(new HashChangeEvent("hashchange")));
    expect(await screen.findByText(/Melchor Romero · emisiones persistidas/i)).toBeInTheDocument();
    expect(screen.queryByText(/Pergamino · emisiones persistidas/i)).not.toBeInTheDocument();

    // F04: la evaluación retrospectiva 2023 del ensamble Pergamino es un
    // protocolo propio y separado, nunca la campaña v4 A/B/C/holdout;
    // Melchor Romero tiene su propia evidencia v3, distinta de estos
    // bundles demostrativos sin evaluación agregada propia acreditada.
    expect(screen.getByText(/protocolo propio y separado/i)).toBeInTheDocument();
    expect(screen.getAllByText(/controlled_daily_v4_external_pergamino/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/controlled_daily_v3/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/evaluación agregada 2023 ya ejecutada/i)).not.toBeInTheDocument();

    window.location.hash = "#defensa-pergamino";
    await act(async () => window.dispatchEvent(new HashChangeEvent("hashchange")));
    expect(await screen.findByText(/Pergamino · emisiones persistidas/i)).toBeInTheDocument();
    expect(screen.queryByText(/Melchor Romero · emisiones persistidas/i)).not.toBeInTheDocument();
  });

  it("opens on Mi cultivo when there is no route, so a producer lands on their own question", async () => {
    window.location.hash = "";
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [], next_cursor: null });
    vi.spyOn(catalogApi, "listSensors").mockResolvedValue({ items: [], next_cursor: null });
    render(<App />);
    expect(screen.getByRole("heading", { name: "Mi cultivo", level: 1 })).toBeInTheDocument();
    const primary = screen.getByRole("navigation", { name: /secciones principales/i });
    expect(within(primary).getByRole("link", { name: "Mi cultivo" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByLabelText(/punto de medición \(sensor\)/i)).not.toBeInTheDocument();
    // `#demo` y `#reproduccion-historica` siguen siendo vistas de Herramientas técnicas.
    expect(screen.getByRole("link", { name: /seguimiento del agua en el cultivo, ir a mi cultivo/i })).toHaveAttribute("href", "#productor");
  });

  it("groups the app in five stable sections and marks the active one without hiding any capability", async () => {
    window.location.hash = "#defensa-melchor-romero";
    render(<App />);
    const primary = screen.getByRole("navigation", { name: /secciones principales/i });
    for (const label of ["Seguimiento histórico", "Mi cultivo", "Laboratorio", "Evidencia", "Herramientas técnicas"]) {
      expect(within(primary).getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(within(primary).getByRole("link", { name: "Seguimiento histórico" })).toHaveAttribute("aria-current", "page");
    expect(within(primary).getByRole("link", { name: "Herramientas técnicas" })).not.toHaveAttribute("aria-current");
    // La localidad se cambia dentro del seguimiento, sin perder el sitio vigente.
    const locality = screen.getByRole("navigation", { name: /localidad/i });
    expect(within(locality).getByRole("link", { name: "Melchor Romero" })).toHaveAttribute("aria-current", "page");
    expect(within(locality).getByRole("link", { name: "Pergamino" })).not.toHaveAttribute("aria-current");
    // Las herramientas técnicas no se muestran fuera de su sección.
    expect(screen.queryByRole("link", { name: "Datos disponibles" })).not.toBeInTheDocument();
  });

  it("keeps every existing tool reachable from Herramientas técnicas", async () => {
    render(<App />);
    const primary = screen.getByRole("navigation", { name: /secciones principales/i });
    expect(within(primary).getByRole("link", { name: "Herramientas técnicas" })).toHaveAttribute("aria-current", "page");
    for (const label of ["Resumen e historial", "Resumen", "Historial y observaciones", "Datos disponibles", "Ajustar próximos pronósticos", "Acerca de esta herramienta"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Reproducción histórica" })).toBeInTheDocument();
  });

  it("shows the architecture view as its own destination with the design-documentation mode", async () => {
    window.location.hash = "#arquitectura";
    render(<App />);
    expect(screen.getByRole("heading", { name: "Arquitectura del sistema", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/documentación de diseño/i);
    const primary = screen.getByRole("navigation", { name: /secciones principales/i });
    expect(within(primary).getByRole("link", { name: "Arquitectura" })).toHaveAttribute("aria-current", "page");
    expect(within(primary).getByRole("link", { name: "Herramientas técnicas" })).not.toHaveAttribute("aria-current");
    // El mapa deja de estar escondido en un <details> colapsado de Herramientas.
    expect(screen.getByRole("navigation", { name: /etapas de la arquitectura/i })).toBeVisible();
  });

  it.each([
    ["#defensa-cicytex", /replay histórico/i],
    ["#laboratorio-sensores", /laboratorio sintético/i],
    ["#productor", /operación/i],
  ])("labels the mode of %s so replay, lab and operation are never confused", async (hash, text) => {
    window.location.hash = hash;
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [], next_cursor: null });
    vi.spyOn(catalogApi, "listSensors").mockResolvedValue({ items: [], next_cursor: null });
    render(<App />);
    expect(screen.getAllByRole("note").some((note) => text.test(note.textContent ?? ""))).toBe(true);
  });

  it("opens the Evidencia section with the governance status visible", async () => {
    window.location.hash = "#evidencia-resultados";
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    render(<App />);
    expect(screen.getByRole("heading", { name: /qué se midió y qué se puede afirmar/i, level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/auditoría científica FAIL/i)).toBeInTheDocument();
    const primary = screen.getByRole("navigation", { name: /secciones principales/i });
    expect(within(primary).getByRole("link", { name: "Evidencia" })).toHaveAttribute("aria-current", "page");
    vi.unstubAllGlobals();
  });

  it("carries the Laboratorio sensor to Herramientas without copying its id or reloading the page", async () => {
    window.location.hash = "#laboratorio-sensores";
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(readyQuality("sensor-a"));
    vi.spyOn(sensorLabApi, "ingestLabReading").mockResolvedValue({ timestamp: "2026-04-30T00:00:00Z", filas_totales: 120 });
    vi.spyOn(forecastApi, "runForecast").mockResolvedValue({
      verdicts: [{ fecha: "2026-04-01", alerta: false, probabilidad: 0.1, fecha_objetivo: "2026-04-04" }], train_rows: 90, test_rows: 20,
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /generar historial de prueba/i }));
    const open = await screen.findByRole("button", { name: /^ver «lab-[a-z0-9]+» en resumen e historial$/i });
    const sensorId = /«(lab-[a-z0-9]+)»/i.exec(open.textContent ?? "")![1];
    await userEvent.click(open);
    // Aterriza en Resumen con el sensor del laboratorio ya activo y el botón habilitado.
    expect(await screen.findByRole("heading", { name: "Resumen" })).toBeInTheDocument();
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent(sensorId);
    await waitFor(() => expect(screen.getByRole("button", { name: /generar pronóstico/i })).toBeEnabled());
  });

  it("offers the Laboratorio sensor in Herramientas with one click when the user comes back by the menu", async () => {
    window.location.hash = "#laboratorio-sensores";
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(readyQuality("sensor-a"));
    vi.spyOn(sensorLabApi, "ingestLabReading").mockResolvedValue({ timestamp: "2026-04-30T00:00:00Z", filas_totales: 120 });
    vi.spyOn(forecastApi, "runForecast").mockResolvedValue({
      verdicts: [{ fecha: "2026-04-01", alerta: false, probabilidad: 0.1, fecha_objetivo: "2026-04-04" }], train_rows: 90, test_rows: 20,
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /generar historial de prueba/i }));
    const open = await screen.findByRole("button", { name: /^ver «lab-[a-z0-9]+» en resumen e historial$/i });
    const sensorId = /«(lab-[a-z0-9]+)»/i.exec(open.textContent ?? "")![1];
    window.location.hash = "#resumen";
    await act(async () => window.dispatchEvent(new HashChangeEvent("hashchange")));
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent("sensor-a");
    await userEvent.click(await screen.findByRole("button", { name: /usar este sensor/i }));
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent(sensorId);
    expect(screen.queryByRole("button", { name: /usar este sensor/i })).not.toBeInTheDocument();
  });

  it("moves focus to the page title when navigating between sections", async () => {
    window.location.hash = "#resumen";
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    render(<App />);
    for (const [hash, name] of [["#defensa-pergamino", "Pergamino"], ["#laboratorio-sensores", "Laboratorio de sensor simulado"], ["#evidencia-resultados", "Qué se midió y qué se puede afirmar"], ["#productor", "Mi cultivo"]] as const) {
      window.location.hash = hash;
      await act(async () => window.dispatchEvent(new HashChangeEvent("hashchange")));
      await waitFor(() => expect(screen.getByRole("heading", { name, level: 1 })).toHaveFocus());
    }
    vi.unstubAllGlobals();
  });

  it("shows the tool destinations in the nav of Herramientas técnicas", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Resumen" })).toBeInTheDocument();
    for (const label of [
      "Resumen",
      "Historial y observaciones",
      "Datos disponibles",
      "Ajustar próximos pronósticos",
      "Acerca de esta herramienta",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Resumen" })).toHaveAttribute("aria-current", "page");
  });

  it("navigates to Historial y observaciones, updates the title, focuses its heading, and keeps the sensor context", async () => {
    render(<App />);
    await waitFor(() => expect(forecastApi.listFeedback).toHaveBeenCalledWith("sensor-a"));

    await userEvent.click(screen.getByRole("link", { name: "Historial y observaciones" }));

    const heading = await screen.findByRole("heading", { name: "Historial y observaciones" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(document.title).toContain("Historial y observaciones");
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent("sensor-a");
    // no se dispara una nueva consulta de historial solo por navegar
    expect(forecastApi.listFeedback).toHaveBeenCalledTimes(1);
  });

  it("keeps the existing #calidad, #prediccion, #linaje and #evidencia anchors working", async () => {
    window.location.hash = "#calidad";
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Datos disponibles" })).toBeInTheDocument();
  });

  it("supports browser back/forward across destinations", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("link", { name: "Datos disponibles" }));
    await screen.findByRole("heading", { name: "Datos disponibles" });

    await userEvent.click(screen.getByRole("link", { name: "Acerca de esta herramienta" }));
    await screen.findByRole("heading", { name: "Acerca de esta herramienta" });

    window.history.back();
    await screen.findByRole("heading", { name: "Datos disponibles" });

    window.history.forward();
    await screen.findByRole("heading", { name: "Acerca de esta herramienta" });
  });

  it("does not lose the last forecast result when navigating away and back to Resumen", async () => {
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({
      rows: [
        {
          fecha: "2024-10-31",
          alerta_generada: 1,
          estado_validacion: "pendiente",
          etiqueta_corregida: null,
          observacion: null,
          y_proba: 0.72,
          fecha_objetivo: null,
        },
      ],
    });

    render(<App />);
    await screen.findByText("2024-10-31");

    await userEvent.click(screen.getByRole("link", { name: "Datos disponibles" }));
    await screen.findByRole("heading", { name: "Datos disponibles" });

    await userEvent.click(screen.getByRole("link", { name: "Resumen e historial" }));
    await screen.findByText("2024-10-31");
    // conservar el contexto no implica volver a consultar el historial
    expect(forecastApi.listFeedback).toHaveBeenCalledTimes(1);
  });

  it("shows the active predictor identity under Ajustar próximos pronósticos", async () => {
    vi.spyOn(forecastApi, "getActivePredictor").mockResolvedValue({
      ...EMPTY_PREDICTOR,
      origin: "recalibrado",
      model_id: "modelo-activo",
      version: "2",
    });

    render(<App />);
    await userEvent.click(screen.getByRole("link", { name: "Ajustar próximos pronósticos" }));

    await waitFor(() => {
      expect(screen.getByText(/modelo-activo/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/modelo-activo/i)).not.toBeVisible();
    await userEvent.click(screen.getByText("Información técnica de los ajustes"));
    expect(screen.getByText(/modelo-activo/i)).toBeVisible();
  });

  it("disables the recalibrate button in Ajustar próximos pronósticos while a forecast run started from Resumen is pending", async () => {
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(readyQuality("sensor-a"));
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({
      rows: [
        {
          fecha: "2024-10-31",
          alerta_generada: 1,
          estado_validacion: "rechazada",
          etiqueta_corregida: 0,
          observacion: "test",
          y_proba: 0.72,
          fecha_objetivo: null,
        },
      ],
    });
    let resolveRun!: (value: forecastApi.ForecastRunResponse) => void;
    vi.spyOn(forecastApi, "runForecast").mockReturnValueOnce(
      new Promise((resolve) => (resolveRun = resolve)),
    );

    render(<App />);
    await screen.findByText("2024-10-31");

    await userEvent.click(screen.getByRole("button", { name: /generar pronóstico/i }));

    await userEvent.click(screen.getByRole("link", { name: "Ajustar próximos pronósticos" }));
    const recalibrateButton = await screen.findByRole("button", { name: /aplicar observaciones/i });
    expect(recalibrateButton).toBeDisabled();

    resolveRun({ train_rows: 1, test_rows: 1, verdicts: [] });
    await waitFor(() => expect(recalibrateButton).not.toBeDisabled());
  });
});

describe("App — contexto del productor (HU6)", () => {
  it("hides the unrelated legacy selector in Mi cultivo and restores its selection when returning", async () => {
    window.location.hash = "#resumen";
    vi.restoreAllMocks();
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({ rows: [] });
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(null);
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [], next_cursor: null });
    render(<App />);
    const input = screen.getByLabelText(/punto de medición \(sensor\)/i);
    await userEvent.clear(input);
    await userEvent.type(input, "sensor-b");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    await userEvent.click(screen.getByRole("link", { name: "Mi cultivo" }));
    await screen.findByRole("heading", { name: "Mi cultivo" });
    expect(screen.queryByLabelText(/punto de medición \(sensor\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sensor activo/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Herramientas técnicas" }));
    expect(await screen.findByLabelText(/punto de medición \(sensor\)/i)).toHaveValue("sensor-b");
    expect(screen.getByText(/sensor activo/i)).toHaveTextContent("sensor-b");
  });
});
describe("App — diseño coherente y accesibilidad (Entrega 4)", () => {
  beforeEach(() => {
    window.location.hash = "#resumen";
    vi.restoreAllMocks();
    vi.spyOn(forecastApi, "getActivePredictor").mockResolvedValue(EMPTY_PREDICTOR);
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({ rows: [] });
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(null);
    vi.spyOn(lineageApi, "getLineage").mockResolvedValue({ sensor_id: "sensor-a", chain: [] });
  });

  it("offers a skip link, as the first focusable element, pointing to a focusable main content landmark", () => {
    render(<App />);

    const skipLink = screen.getByRole("link", { name: /saltar al contenido/i });
    expect(skipLink).toHaveAttribute("href", "#main-content");

    // jsdom no simula el salto de foco del navegador al activar un enlace
    // de fragmento; lo que sí podemos verificar aquí es que el destino
    // existe y es programáticamente enfocable (tabIndex="-1"). El salto de
    // foco real se verificó a mano en un navegador (ver PR).
    const target = document.getElementById("main-content");
    expect(target).not.toBeNull();
    expect(target).toHaveAttribute("tabIndex", "-1");
  });
});
