# Change: Verify content-addressed Laya provenance

## Why

PR34 proves the bytes of the five declared checkpoint files but deliberately does
not prove how the source or checkpoint Git histories describe those bytes.  A
separate, narrow contract is needed to bind selected Git objects and observed
Apache declarations without turning repository metadata into an origin, legal or
execution attestation.

## What Changes

- Add a pure bytes-only provenance core for pinned Git SHA-1 object identities and
  independent SHA-256 byte authorities.
- Verify the exact Laya source commit
  `68804629e8ccd9d616d48a40e87de9fabbeae069`, annotated unsigned tag `v0.4.2`,
  `LICENSE` and the Apache declaration in `pyproject.toml`.
- Verify the exact checkpoint commit
  `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, its `multilingual` tree, five
  small-file or Git LFS pointer links and README Apache metadata.
- Bind checkpoint Git metadata to exact PR34 checkpoint evidence.  PR34 remains
  the sole authority for the five checkpoint payload bytes.
- Add conservative content/declaration-observed flags, private evidence and an opt-in real
  gate over externally captured inputs.

## Impact

- Planned pure module: `human_feedback.runtime_provenance`, with public API limited
  to `prepare_laya_runtime_provenance_plan`,
  `verify_laya_runtime_provenance_objects` and
  `canonical_laya_runtime_provenance_summary_bytes`.
- No filesystem adapter, network, clone, fetch, download or productive caller.
- No legal conclusion, signature/authenticity proof, runtime materialization,
  executor or inference claim.

