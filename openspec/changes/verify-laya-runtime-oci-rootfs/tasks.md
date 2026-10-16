## 1. RED — metadata prerequisite

- [x] 1.1 Require effective mode, uid, gid and mtime on every TAR entry.
- [x] 1.2 Require optional root-directory metadata outside ordinary manifest entries.
- [x] 1.3 Reject conflicting repeated root markers.

## 2. RED — composition

- [x] 2.1 Specify exact PR32 evidence binding and sealed plan/evidence types.
- [x] 2.2 Specify ordered whiteout and opaque-directory overlay behavior.
- [x] 2.3 Specify file/directory replacement and final canonical node ordering.
- [x] 2.4 Specify root-bound link behavior with compatible dangling symlink leaves.
- [x] 2.5 Specify fixed budgets, all-or-nothing sealing and private summaries.

## 3. GREEN

- [ ] 3.1 Preserve TAR numeric and root-marker metadata.
- [ ] 3.2 Implement pure rootfs plan and overlay compositor.
- [ ] 3.3 Implement deep revalidation, budgets and canonical evidence.

## 4. Gates

- [ ] 4.1 Run PR32 TAR/layer/filesystem regressions.
- [ ] 4.2 Run Melchor Romero and Pergamino historical/demo regressions.
- [ ] 4.3 Run CICYTEX experiment and mocked-sensor regressions.
- [ ] 4.4 Characterize the real Laya link topology before tightening dangling-link policy.

## 5. Deferred

- [ ] 5.1 Materialize a rootfs only in a later isolated change.
- [ ] 5.2 Verify origin, license and base ancestry separately.
- [ ] 5.3 Enable executor or inference only after their own evidence gates.

