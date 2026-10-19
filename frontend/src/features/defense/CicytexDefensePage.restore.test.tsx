import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CicytexDefensePage } from "./CicytexDefensePage";
import * as api from "./cicytexApi";

const KEY = "cicytex-defense-session";

const CATALOG: api.CicytexCatalog = {
  sensors: ["CP1_S1", "CP1_S2"],
  emission_dates: ["2023-07-06", "2023-07-07"],
  emission_dates_by_horizon: {
    "1": ["2023-07-06", "2023-07-07"],
    "2": ["2023-07-06", "2023-07-07"],
    "3": ["2023-07-06", "2023-07-07"],
  },
  horizons: [1, 2, 3],
  first_legitimate_emission: "2023-07-06",
  last_observation: "2023-07-25",
};

const METRIC = { n: 0, tp: 0, tn: 0, fp: 0, fn: 0, mcc: null, precision: null, recall: null, f1: null, coverage: 0 };
const REVEALED: api.CicytexSession["predictions"] = [
  {
    method: "ensemble",
    score: 0.4,
    alert: false,
    target_date: "2023-07-07",
    observed_soil_moisture: 0.3,
    observed_label: 0,
    outcome: "VN",
  },
];

function session(overrides: Partial<api.CicytexSession> = {}): api.CicytexSession {
  return {
    session_id: "session-1",
    sensor_id: "CP1_S1",
    emission_date: "2023-07-06",
    horizon_days: 1,
    revealed_through: "2023-07-06",
    threshold: 0.25,
    proxy_notice: "proxy",
    predictions: REVEALED,
    readings: [{ date: "2023-07-06", soil_moisture: 0.3 }],
    metrics: {
      ensemble: METRIC,
      logistic_regression: METRIC,
      random_forest: METRIC,
      hist_gradient_boosting_classifier: METRIC,
      persistence: METRIC,
    },
    feedback: null,
    can_advance: true,
    ...overrides,
  };
}

const record = (overrides: Record<string, unknown> = {}) =>
  JSON.stringify({
    site: "cicytex",
    session_id: "session-1",
    sensor: "CP1_S1",
    horizon: 1,
    emission: "2023-07-06",
    ...overrides,
  });

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

let get: ReturnType<typeof vi.spyOn>;
let create: ReturnType<typeof vi.spyOn>;
let advance: ReturnType<typeof vi.spyOn>;
let reset: ReturnType<typeof vi.spyOn>;
let feedback: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  vi.spyOn(api, "getCicytexCatalog").mockResolvedValue(CATALOG);
  vi.spyOn(api, "getCicytexProvenance").mockRejectedValue(new Error("n/a"));
  get = vi.spyOn(api, "getCicytexSession");
  create = vi.spyOn(api, "createCicytexSession");
  advance = vi.spyOn(api, "advanceCicytexSession");
  reset = vi.spyOn(api, "resetCicytexSession");
  feedback = vi.spyOn(api, "submitCicytexFeedback");
});

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

function expectNoPost() {
  expect(create).not.toHaveBeenCalled();
  expect(advance).not.toHaveBeenCalled();
  expect(reset).not.toHaveBeenCalled();
  expect(feedback).not.toHaveBeenCalled();
}

describe("CicytexDefensePage session persistence on open", () => {
  it("stores only the session reference (no draft) in sessionStorage when a session opens", async () => {
    create.mockResolvedValue(session({ session_id: "abc" }));
    render(<CicytexDefensePage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByText(/Decisión de la arquitectura/);
    fireEvent.click(screen.getByLabelText(/No coincide/));
    fireEvent.change(screen.getByLabelText(/Observación opcional/), { target: { value: "borrador" } });

    expect(JSON.parse(window.sessionStorage.getItem(KEY)!)).toEqual({
      site: "cicytex",
      session_id: "abc",
      sensor: "CP1_S1",
      horizon: 1,
      emission: "2023-07-06",
    });
    expect(window.sessionStorage.getItem(KEY)).not.toContain("borrador");
    expect(window.localStorage.length).toBe(0);
  });
});

describe("CicytexDefensePage session restore", () => {
  it("restores a matching session, the selection and an empty draft using only GET", async () => {
    window.sessionStorage.setItem(
      KEY,
      record({ session_id: "s9", sensor: "CP1_S2", horizon: 2, emission: "2023-07-07" }),
    );
    get.mockResolvedValue(
      session({ session_id: "s9", sensor_id: "CP1_S2", horizon_days: 2, emission_date: "2023-07-07" }),
    );
    render(<CicytexDefensePage />);

    await screen.findByText(/Decisión de la arquitectura/);
    expect(get).toHaveBeenCalledWith("s9");
    expect(screen.getByLabelText("Sonda")).toHaveValue("CP1_S2");
    expect(screen.getByLabelText("Horizonte")).toHaveValue("2");
    expect(screen.getByLabelText("Fecha de emisión")).toHaveValue("2023-07-07");
    expect(screen.getByLabelText(/Observación opcional/)).toHaveValue("");
    expect(screen.getByLabelText(/Sí, coincide/)).not.toBeChecked();
    expect(screen.getByLabelText(/No coincide/)).not.toBeChecked();
    expect(screen.queryByText(/No se pudo recuperar/)).not.toBeInTheDocument();
    expectNoPost();
  });

  const notRecoverable: Array<[string, () => void]> = [
    ["inexistente (404)", () => get.mockRejectedValue(new Error("Sesion inexistente"))],
    // El backend no tiene vencimiento/TTL (SQLite sin expiración): una sesión
    // "vencida" o purgada se observa igual que una inexistente, con 404.
    ["vencida (el servidor responde 404 como inexistente)", () => get.mockRejectedValue(new Error("Sesion inexistente"))],
    ["emisión inexistente (404)", () => get.mockRejectedValue(new Error("No existe esa emision CICYTEX"))],
    ["error de red", () => get.mockRejectedValue(new TypeError("Failed to fetch"))],
    ["sonda distinta", () => get.mockResolvedValue(session({ sensor_id: "CP1_S2" }))],
    ["horizonte distinto", () => get.mockResolvedValue(session({ horizon_days: 2 }))],
    ["emisión distinta", () => get.mockResolvedValue(session({ emission_date: "2023-07-07" }))],
    ["id de sesión distinto", () => get.mockResolvedValue(session({ session_id: "otra" }))],
  ];
  it.each(notRecoverable)("explains and clears the record when %s", async (_name, arrange) => {
    window.sessionStorage.setItem(KEY, record());
    arrange();
    render(<CicytexDefensePage />);

    expect(await screen.findByText(/No se pudo recuperar la sesión anterior:/)).toBeVisible();
    expect(window.sessionStorage.getItem(KEY)).toBeNull();
    expect(screen.queryByText(/Decisión de la arquitectura/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled();
    expectNoPost();

    fireEvent.click(screen.getByRole("button", { name: "Iniciar otra emisión" }));
    expect(screen.queryByText(/No se pudo recuperar/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toHaveFocus();
    expectNoPost();
  });

  const invalidRecords: Array<[string, string]> = [
    ["JSON inválido", "{no-json"],
    ["no es objeto", "42"],
    ["otro sitio", record({ site: "melchor" })],
    ["sonda fuera de catálogo", record({ sensor: "XX" })],
    ["horizonte fuera de catálogo", record({ horizon: 7 })],
    ["emisión fuera de catálogo", record({ emission: "1999-01-01" })],
    ["id vacío", record({ session_id: "" })],
    ["tipos incorrectos", record({ horizon: "1" })],
  ];
  it.each(invalidRecords)("discards a corrupt record without requesting anything: %s", async (_name, raw) => {
    window.sessionStorage.setItem(KEY, raw);
    render(<CicytexDefensePage />);

    expect(await screen.findByText(/No se pudo recuperar la sesión anterior:/)).toBeVisible();
    expect(get).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem(KEY)).toBeNull();
    expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled();
    expectNoPost();
  });

  it("works when sessionStorage throws on read and write", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    create.mockResolvedValue(session());
    render(<CicytexDefensePage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));

    expect(await screen.findByText(/Decisión de la arquitectura/)).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it("works when window.sessionStorage itself is unavailable", async () => {
    vi.spyOn(window, "sessionStorage", "get").mockImplementation(() => {
      throw new Error("denied");
    });
    create.mockResolvedValue(session());
    render(<CicytexDefensePage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));

    expect(await screen.findByText(/Decisión de la arquitectura/)).toBeInTheDocument();
  });
});

describe("CicytexDefensePage late restore responses", () => {
  it("ignores a late restore after the selection changed", async () => {
    window.sessionStorage.setItem(KEY, record());
    const pending = deferred<api.CicytexSession>();
    get.mockReturnValue(pending.promise);
    render(<CicytexDefensePage />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText("Sonda"), { target: { value: "CP1_S2" } });
    await act(async () => {
      pending.resolve(session());
    });

    expect(screen.queryByText(/Decisión de la arquitectura/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Sonda")).toHaveValue("CP1_S2");
    expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled();
    expectNoPost();
  });

  it("does not show a late restore failure after the selection changed", async () => {
    window.sessionStorage.setItem(KEY, record());
    let fail!: (reason: Error) => void;
    get.mockReturnValue(
      new Promise((_resolve, reject) => {
        fail = reject;
      }),
    );
    render(<CicytexDefensePage />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText("Horizonte"), { target: { value: "2" } });
    await act(async () => {
      fail(new Error("Sesion inexistente"));
    });

    expect(screen.queryByText(/No se pudo recuperar/)).not.toBeInTheDocument();
  });

  it("a late restore of an old record never replaces a session the person opened", async () => {
    window.sessionStorage.setItem(KEY, record({ session_id: "vieja" }));
    const pending = deferred<api.CicytexSession>();
    get.mockReturnValue(pending.promise);
    create.mockResolvedValue(session({ session_id: "nueva", sensor_id: "CP1_S2" }));
    render(<CicytexDefensePage />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText("Sonda"), { target: { value: "CP1_S2" } });
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByText(/Decisión de la arquitectura/);
    await act(async () => {
      pending.resolve(session({ session_id: "vieja" }));
    });

    expect(screen.getByLabelText("Sonda")).toHaveValue("CP1_S2");
    expect(JSON.parse(window.sessionStorage.getItem(KEY)!).session_id).toBe("nueva");
    expect(create).toHaveBeenCalledTimes(1);
    expect(advance).not.toHaveBeenCalled();
  });
});

describe("CicytexDefensePage drafts are never transferred", () => {
  async function openWithDraft(note: string) {
    await waitFor(() => expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    fireEvent.click(await screen.findByLabelText(/No coincide/));
    fireEvent.change(screen.getByLabelText(/Observación opcional/), { target: { value: note } });
  }

  it.each([
    ["Sonda", "CP1_S2"],
    ["Horizonte", "2"],
    ["Fecha de emisión", "2023-07-07"],
  ])("drops note and choice when %s changes", async (label, value) => {
    create.mockResolvedValue(session());
    render(<CicytexDefensePage />);
    await openWithDraft("no debe viajar");

    fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByRole("button", { name: "Registrar feedback" });

    expect(screen.getByLabelText(/Observación opcional/)).toHaveValue("");
    expect(screen.getByLabelText(/Sí, coincide/)).not.toBeChecked();
    expect(screen.getByLabelText(/No coincide/)).not.toBeChecked();
  });

  it("starts empty after a reset and after a restore even if a draft existed before", async () => {
    create.mockResolvedValue(session());
    reset.mockResolvedValue(session());
    const first = render(<CicytexDefensePage />);
    await openWithDraft("nota previa");
    fireEvent.click(screen.getByRole("button", { name: "Reiniciar" }));
    await waitFor(() => expect(reset).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByLabelText(/Observación opcional/)).toHaveValue(""));
    expect(screen.getByLabelText(/No coincide/)).not.toBeChecked();
    first.unmount();

    get.mockResolvedValue(session());
    render(<CicytexDefensePage />);
    await screen.findByRole("button", { name: "Registrar feedback" });
    expect(screen.getByLabelText(/Observación opcional/)).toHaveValue("");
    expect(screen.getByLabelText(/No coincide/)).not.toBeChecked();
    expect(window.sessionStorage.getItem(KEY)).not.toContain("nota previa");
  });
});

describe("CicytexDefensePage feedback form", () => {
  async function openRevealed() {
    create.mockResolvedValue(session());
    render(<CicytexDefensePage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByRole("button", { name: "Registrar feedback" });
  }

  it("has no preselected option and keeps the button disabled until a choice is made", async () => {
    await openRevealed();
    const yes = screen.getByLabelText(/Sí, coincide/);
    const no = screen.getByLabelText(/No coincide/);
    const submit = screen.getByRole("button", { name: "Registrar feedback" });
    expect(yes).not.toBeChecked();
    expect(no).not.toBeChecked();
    expect(submit).toBeDisabled();
    expect(yes.closest("label")!.className).toBe(no.closest("label")!.className);

    fireEvent.click(no);
    expect(submit).toBeEnabled();
  });

  it.each([
    ["Sí, coincide", "confirmada"],
    ["No coincide", "rechazada"],
  ])("sends estado_validacion for %s", async (label, expected) => {
    feedback.mockResolvedValue({
      estado_validacion: expected,
      observacion: null,
      registered_at: "2023-07-07T00:00:00Z",
    } as api.ReplayFeedback);
    await openRevealed();
    fireEvent.click(screen.getByLabelText(new RegExp(label)));
    fireEvent.click(screen.getByRole("button", { name: "Registrar feedback" }));
    await waitFor(() => expect(feedback).toHaveBeenCalledWith("session-1", { estado_validacion: expected, observacion: undefined }));
  });

  it("is reachable with Tab (both options and the button) and sends once on double click", async () => {
    const pending = deferred<api.ReplayFeedback>();
    feedback.mockReturnValue(pending.promise);
    await openRevealed();
    const user = userEvent.setup();
    const yes = screen.getByLabelText(/Sí, coincide/);
    const no = screen.getByLabelText(/No coincide/);
    const note = screen.getByLabelText(/Observación opcional/);

    yes.focus();
    expect(yes).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(no).toHaveFocus();
    expect(no).toBeChecked();
    await user.tab();
    expect(note).toHaveFocus();
    await user.tab();
    const submit = screen.getByRole("button", { name: "Registrar feedback" });
    expect(submit).toHaveFocus();

    await user.dblClick(submit);
    expect(feedback).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Registrando…" })).toBeDisabled();
  });

  it("makes both options reachable by Tab when none is selected", async () => {
    await openRevealed();
    const user = userEvent.setup();
    const yes = screen.getByLabelText(/Sí, coincide/);
    // Sin elección, el grupo de radios entra en el orden de Tab como un único tope.
    document.body.focus();
    let reached = false;
    for (let i = 0; i < 12 && !reached; i += 1) {
      await user.tab();
      reached = document.activeElement === yes;
    }
    expect(reached).toBe(true);
  });
});
