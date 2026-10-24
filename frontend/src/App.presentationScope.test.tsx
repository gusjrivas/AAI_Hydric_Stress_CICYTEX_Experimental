import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { SiteHeader } from "./features/defense/SiteHeader";

describe("Alcance de la presentación", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    window.location.hash = "";
  });

  it.each(["pergamino", "melchor"] as const)("el selector de %s ofrece sólo los dos sitios principales", (site) => {
    render(<SiteHeader site={site} />);
    expect(screen.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual([
      "#defensa-pergamino", "#defensa-melchor-romero",
    ]);
    expect(document.body.textContent).not.toMatch(/cicytex|talavera/i);
  });

  it("una URL antigua abre Mi cultivo sin montar ni consultar CICYTEX", () => {
    window.location.hash = "#defensa-cicytex";
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "Mi cultivo" })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/cicytex|talavera/i);
    expect(document.querySelector('a[href*="cicytex"]')).toBeNull();
    expect(vi.mocked(fetch).mock.calls.some(([url]) => /cicytex/i.test(String(url)))).toBe(false);
  });
});
