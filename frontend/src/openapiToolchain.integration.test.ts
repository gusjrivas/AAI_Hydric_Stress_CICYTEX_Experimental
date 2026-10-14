import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

const temporaryDirectories: string[] = [];

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("local openapi-typescript executable", () => {
  it("executes the installed generator twice with byte-identical output", () => {
    const directory = mkdtempSync(join(tmpdir(), "openapi-typescript-"));
    temporaryDirectories.push(directory);
    const input = join(directory, "openapi.json");
    const first = join(directory, "first.ts");
    const second = join(directory, "second.ts");
    writeFileSync(
      input,
      JSON.stringify({
        openapi: "3.1.0",
        info: { title: "local-contract", version: "1" },
        paths: {
          "/health": {
            get: {
              operationId: "health",
              responses: { "200": { description: "ok" } },
            },
          },
        },
      }),
    );

    const executable = resolve(
      "node_modules",
      ".bin",
      process.platform === "win32" ? "openapi-typescript.cmd" : "openapi-typescript",
    );
    const run = (output: string) =>
      spawnSync(executable, [input, "-o", output], {
        cwd: resolve("."),
        encoding: "utf8",
        shell: process.platform === "win32",
      });
    const firstRun = run(first);
    const secondRun = run(second);

    expect(firstRun.status, firstRun.stderr).toBe(0);
    expect(secondRun.status, secondRun.stderr).toBe(0);
    expect(readFileSync(first)).toEqual(readFileSync(second));
    expect(readFileSync(first, "utf8")).toContain("export interface paths");
  });
});
