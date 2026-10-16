# Change: Verify Laya checkpoint bytes

## Why

PR17 validates the closed checkpoint manifest but deliberately leaves
`checkpoint_bytes_verified=false`.  Runtime execution must not trust model files
until the five declared files have been captured from one filesystem root and
stream-verified against their exact sizes and SHA-256 digests.

## What Changes

- Add a pure descriptor-bound checkpoint plan and bounded streaming verifier.
- Add immutable per-file receipts and all-or-nothing checkpoint evidence.
- Add a Linux secure-descriptor adapter with closed inventory, TOCTOU sweeps and
  close-before-seal ordering.
- Add an external opt-in release gate for the real 678,201,636-byte checkpoint.
- Add a dedicated Ubuntu/Windows focal CI contract; normal CI never downloads
  checkpoint bytes or claims the external gate ran.

## Impact

- New pure module `human_feedback.runtime_checkpoint`.
- New adapter `human_feedback.adapters.filesystem_checkpoint`.
- No sixth runtime-bundle artifact, model load, network access, materialization,
  executor or inference claim.
- No backend, runner, dataset or experiment caller.
