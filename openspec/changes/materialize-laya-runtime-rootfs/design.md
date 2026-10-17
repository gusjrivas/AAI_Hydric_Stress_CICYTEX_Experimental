# Design: Safe disposable Laya rootfs materialization

## Boundaries

The pure module accepts only exact PR33 `LayaRuntimeOciRootfsEvidence` and exact
issued PR37 `LayaRuntimeSupplyConvergenceEvidence`. It revalidates both and
requires object-identity equality between the PR33 layer evidence and PR37 layer
evidence, plus the same runtime identity. Caller paths never create authority.

Filesystem mutation belongs to a separate Linux adapter. Windows and hosts
without descriptor-relative no-follow traversal and atomic no-clobber rename
fail before path coercion or mutation. No network, subprocess, mount, chroot,
package installation, checkpoint installation or inference is permitted.

## Honest materialization claim

`rootfs_materialized=true` means the authenticated regular-file payloads and the
final PR33 directory/link topology were written into an owner-only disposable
tree and atomically published. It does not mean exact OCI ownership, xattrs,
ACLs, capabilities, devices, a runnable environment or container equivalence.
UID/GID and metadata not safely realizable by a non-root host remain in sealed
logical evidence. Setuid/setgid bits are not enabled by the host profile.

## Content authority

PR33 commits topology and metadata but not file contents. The adapter must
therefore reopen the exact OCI layout through held descriptors, consume all ten
layers, and reverify compressed digests, DiffIDs and TAR semantics while routing
bounded payload chunks to staging. A private deterministic commitment contains
sorted regular-file digests and link groups. The staged tree is re-read and
compared before publication. Paths, targets, digests and destinations never
appear in repr, public summaries or errors.

## Atomicity and cleanup

Staging is an exclusive random 0700 sibling under a private destination parent.
The destination must be absent. Publication uses a same-filesystem atomic
no-clobber operation; plain replacing rename is forbidden. Evidence is sealed
only after staged verification, fsync, final source sweep, publication, parent
fsync and final inode verification.

Failure before publication leaves no destination and removes only the staging
inode owned by the operation using descriptor-relative, no-follow traversal.
Concurrent losers never delete a winner. Crash recovery may remove only stale
staging carrying an authenticated ownership marker; it never grants evidence.

## Claims

The result inherits verified predecessor claims. Relative to their union the
only new true claim is `rootfs_materialized`. `runtime_materialized`,
`executor_available`, `inference_executed`, origin/license conclusions,
readiness and production remain false.
