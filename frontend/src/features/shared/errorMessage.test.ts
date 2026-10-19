import { describe, expect, it } from "vitest";
import { GENERIC_ERROR_MESSAGE, NETWORK_ERROR_MESSAGE, userFacingErrorMessage } from "./errorMessage";

describe("userFacingErrorMessage", () => {
  it.each(["Failed to fetch", "NetworkError when attempting to fetch resource.", "Load failed"])(
    "translates the browser network failure %j to Spanish",
    (raw) => {
      const message = userFacingErrorMessage(new TypeError(raw));
      expect(message).toBe(NETWORK_ERROR_MESSAGE);
      expect(message).not.toMatch(/failed to fetch|networkerror|load failed/i);
    },
  );

  it("keeps the Spanish server detail of an ordinary error untouched", () => {
    expect(userFacingErrorMessage(new Error("Sensor no encontrado"))).toBe("Sensor no encontrado");
  });

  it("does not leak a non-Error value", () => {
    expect(userFacingErrorMessage("boom")).toBe(GENERIC_ERROR_MESSAGE);
  });
});
