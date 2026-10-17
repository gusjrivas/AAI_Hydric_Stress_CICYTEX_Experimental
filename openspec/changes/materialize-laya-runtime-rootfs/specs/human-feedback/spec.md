## ADDED Requirements

### Requirement: Materialization SHALL bind exact predecessor authorities

The system SHALL accept only exact PR33 rootfs evidence and exact issued PR37
supply-convergence evidence. Both SHALL be revalidated before path coercion or
I/O and SHALL share the exact layer evidence and runtime identity.

#### Scenario: Evidence is forged or mixed

- **WHEN** either predecessor is proxied, cloned, deeply changed or comes from a different supply graph
- **THEN** planning fails privately before any filesystem operation

### Requirement: The host profile SHALL make a conservative claim

The system SHALL define `rootfs_materialized=true` as authenticated regular bytes
and final directory, symlink and hardlink topology under
`nonroot-disposable-v1`. It SHALL NOT claim exact OCI uid/gid, xattrs, ACLs,
capabilities, device semantics or runtime executability.

#### Scenario: Host metadata cannot be represented non-root

- **WHEN** logical OCI ownership or metadata cannot be safely applied
- **THEN** it remains bound in private logical evidence
- **AND** the public claim does not state that host metadata is exact

### Requirement: Payloads SHALL be recaptured and content-bound

The Linux adapter SHALL recapture all ten layer streams from the exact OCI layout
and reverify compressed digest, DiffID and TAR semantics while extracting. It
SHALL privately commit every surviving regular-file digest and re-read the staged
tree before publication.

#### Scenario: One staged byte changes without changing file size

- **WHEN** final verification observes a content digest mismatch
- **THEN** no rootfs is published and no evidence is emitted

### Requirement: Publication SHALL be bounded, atomic and no-clobber

The system SHALL stage under an owner-controlled destination parent without group/world write, enforce fixed byte
and node limits, fsync the verified tree and publish with a same-filesystem atomic
no-clobber primitive. Missing secure Linux capabilities SHALL fail closed.

#### Scenario: The destination appears concurrently

- **WHEN** another process wins the destination name before publication
- **THEN** the current operation fails without replacing or deleting the winner

### Requirement: Cleanup SHALL be scoped to owned disposable state

Cleanup SHALL use descriptor-relative no-follow traversal, SHALL not cross a
mount, and SHALL remove only staging or a published tree whose recorded inode
identity belongs to the exact evidence.

The adapter SHALL expose explicit evidence-bound disposal, revoke the issued
authority on disposal, and close retained descriptors. A crashed process's
orphan state SHALL never be adopted or deleted automatically by a new run.

#### Scenario: Cleanup encounters a rebound path

- **WHEN** the parent or root inode no longer matches the sealed identity
- **THEN** cleanup fails closed without traversing or deleting the replacement

### Requirement: Materialization SHALL remain operationally isolated

The pure authority and filesystem adapter SHALL not be called by backend,
datasets, experiment runners, readiness or UI code in PR39. Runtime installation,
executor availability, inference and scientific readiness SHALL remain false.

#### Scenario: Existing scenarios are regressed

- **WHEN** PR39 is gated
- **THEN** Melchor Romero, Pergamino, CICYTEX and mocked-sensor behavior is unchanged
