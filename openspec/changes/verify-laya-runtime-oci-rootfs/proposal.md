# Change: Verify Laya OCI rootfs composition

## Why

PR32 verifies the exact ten TAR streams and their DiffIDs, but deliberately treats
whiteout names and link targets as metadata and keeps `oci_rootfs_verified=false`.
Before any materialization or execution claim, the ordered layers need a pure,
bounded and fail-closed overlay composition.

PR32 currently validates header numeric fields but does not retain effective
`mode`, `uid`, `gid` or `mtime`, and excludes the `./` root marker entirely. PR33
must close that information loss before it can make a rootfs composition claim.

## What Changes

- Preserve effective TAR metadata and optional root-directory marker metadata in
  the sealed PR32 receipts without retaining file payloads.
- Add a pure rootfs composition plan bound to one exact PR32 evidence object.
- Apply OCI whiteouts and opaque directories in exact base-to-top layer order.
- Validate the effective path tree and root-bound link behavior without touching
  the host filesystem.
- Enforce fixed budgets for nodes, whiteouts, metadata, path depth, link traversal
  and mutations, with all-or-nothing evidence.
- Elevate only `oci_rootfs_verified`; materialization, origin, license, ancestry,
  executor and inference remain false.
- Preserve all Melchor Romero, Pergamino, CICYTEX and mocked-sensor behavior by
  keeping the new module isolated from productive callers.

## Impact

- New pure module: `human_feedback.runtime_oci_rootfs`.
- Extended private TAR receipt projection for effective numeric metadata and root
  marker metadata.
- No extraction, filesystem writes, runtime launch or model execution.
- No backend, runner, script or dataset caller is introduced.

