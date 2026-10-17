## ADDED Requirements

### Requirement: Runtime materialization SHALL bind exact live predecessors

The system SHALL deeply revalidate an exact live issued rootfs materialization
and the exact issued checkpoint already linked by its supply graph, with the same
runtime identity. Only `runtime_materialized` SHALL become newly true.

#### Scenario: A parent is cloned, mixed, mutated or revoked

- **WHEN** runtime materialization planning receives such a predecessor
- **THEN** it fails privately before paths, subprocesses or Docker operations

### Requirement: Derived runtime contents SHALL be independently verified

The system SHALL assemble only the authenticated rootfs and five exact checkpoint
objects into a new artifact, then recapture its contents independently of child
runtime code. Source artifacts SHALL remain unchanged.

#### Scenario: A byte, namespace entry or checkpoint digest changes

- **WHEN** assembly or independent recapture detects a mismatch
- **THEN** no runtime evidence is emitted and only owned derived resources are removed

### Requirement: The load probe SHALL be isolated, closed and offline

The system SHALL inspect and enforce a non-root, read-only, networkless child with
bounded resources and no host exposure. It SHALL use the image's interpreter to
import and load the exact local CPU model without inference.

#### Scenario: Isolation, import or model loading fails

- **WHEN** a restriction is unavailable, content drifts, output is invalid or the probe fails
- **THEN** materialization fails closed with no executor, inference or readiness claim

### Requirement: Runtime lifecycle SHALL remain evidence-bound

Owned container/image IDs and nonce labels SHALL govern cleanup. Disposal SHALL
revoke runtime authority and support safe retry. The live parent rootfs SHALL be
leased against concurrent disposal while assembly depends on it.

#### Scenario: Cleanup fails transiently

- **WHEN** disposal has already revoked authority but resource cleanup fails once
- **THEN** a retry can clean only the same owned resource without reissuing authority
