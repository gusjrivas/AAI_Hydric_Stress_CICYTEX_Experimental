import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(frontendRoot, "..");
const trackedRoot = resolve(frontendRoot, "src", "api", "generated");
const trackedNames = ["openapi.json", "schema.d.ts", "manifest.json"];
const rawNames = ["openapi.json", "openapi.ts", "openapi-manifest.json"];

function assertNoAnyKeyword(sourceBytes) {
  const source = ts.createSourceFile(
    "schema.d.ts",
    sourceBytes.toString("utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const visit = (node) => {
    if (node.kind === ts.SyntaxKind.AnyKeyword) {
      throw new Error("generated TypeScript contains an AnyKeyword node");
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}

function candidateArtifacts() {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "openapi-typescript-toolchain-"));
  try {
    const rawRoot = join(temporaryRoot, "raw");
    const python = process.env.PYTHON || "python";
    const result = spawnSync(
      python,
      [
        resolve(repositoryRoot, "src", "openapi_typescript_exporter.py"),
        "generate",
        "--output",
        rawRoot,
        "--frontend-root",
        frontendRoot,
      ],
      { cwd: repositoryRoot, encoding: "utf8" },
    );
    if (result.status !== 0) {
      throw new Error(result.stderr || "OpenAPI export failed");
    }
    const artifacts = new Map([
      [trackedNames[0], readFileSync(join(rawRoot, rawNames[0]))],
      [trackedNames[1], readFileSync(join(rawRoot, rawNames[1]))],
      [trackedNames[2], readFileSync(join(rawRoot, rawNames[2]))],
    ]);
    assertNoAnyKeyword(artifacts.get("schema.d.ts"));
    return artifacts;
  } finally {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
}

function generate() {
  const artifacts = candidateArtifacts();
  mkdirSync(trackedRoot, { recursive: true });
  for (const [name, bytes] of artifacts) {
    writeFileSync(join(trackedRoot, name), bytes);
  }
}

function check() {
  const artifacts = candidateArtifacts();
  for (const [name, bytes] of artifacts) {
    let tracked;
    try {
      tracked = readFileSync(join(trackedRoot, name));
    } catch {
      throw new Error(`tracked artifact is unavailable: ${name}`);
    }
    if (!tracked.equals(bytes)) {
      throw new Error(`tracked artifact drift: ${name}`);
    }
  }
}

const mode = process.argv[2];
if (mode === "generate") {
  generate();
} else if (mode === "check") {
  check();
} else {
  throw new Error("expected generate or check mode");
}
