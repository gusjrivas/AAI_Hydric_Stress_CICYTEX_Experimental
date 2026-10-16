## 1. RED — metadata prerequisite

- [x] 1.1 Require effective mode, uid, gid and mtime on every TAR entry (`3a93793`, `0e76684`).
- [x] 1.2 Require optional root-directory metadata outside ordinary manifest entries (`3a93793`).
- [x] 1.3 Reject conflicting repeated root markers (`0e76684`, `62c64c1`).

## 2. RED — composition

- [x] 2.1 Specify exact PR32 evidence binding and sealed plan/evidence types (`3a93793`, `d3aa626`, `7c921ce`).
- [x] 2.2 Specify lower-state whiteouts, same-layer directory parent view and opaque behavior (`3a93793`, `a388d6b`).
- [x] 2.3 Specify replacement, final canonical ordering and hardlink final-state resolution (`0e76684`, `62c64c1`).
- [x] 2.4 Specify root-bound link behavior with compatible dangling symlink leaves (`a388d6b`).
- [x] 2.5 Specify metadata/payload caps, parent→children bounded work, all-or-nothing sealing and private summaries (`92b8993`, `7c921ce`).

## 3. GREEN

- [x] 3.1 Preserve TAR numeric and root-marker metadata (`87a50eb`).
- [x] 3.2 Implement pure rootfs plan and overlay compositor (`87a50eb`).
- [x] 3.3 Implement exact rederivation, budgets, bounded child index and canonical evidence (`87a50eb`).

## 4. Gates

- [x] 4.1 Run PR32 TAR/layer/filesystem regressions; gatekeeper GO on `87a50eb`.
- [x] 4.2 Run Melchor Romero and Pergamino historical/demo regressions; gatekeeper GO on `87a50eb`.
- [x] 4.3 Run CICYTEX experiment and mocked-sensor regressions; gatekeeper GO on `87a50eb`.
- [x] 4.4 Characterize the real Laya topology: dangling symlink leaves remain compatible; 56,996 entries compose to 56,114 final nodes with rootfs verified and not materialized.
- [x] 4.5 Extend the existing Ubuntu/Windows `laya-oci-tar-contract` CI job with the rootfs suite, preserving its job id, name and single dependency installation.

## 5. Deferred

- [ ] 5.1 Materialize a rootfs only in a later isolated change.
- [ ] 5.2 Verify origin, license and base ancestry separately.
- [ ] 5.3 Enable executor or inference only after their own evidence gates.

