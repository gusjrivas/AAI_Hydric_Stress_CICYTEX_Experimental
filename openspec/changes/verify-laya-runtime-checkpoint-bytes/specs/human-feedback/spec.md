# Human feedback runtime checkpoint byte verification

## ADDED Requirements

### Requirement: Checkpoint plans SHALL derive from exact deployment evidence

The system SHALL derive exactly five ordered checkpoint descriptors from one
deeply valid deployment evidence graph and SHALL accept no caller-supplied file
identity.

#### Scenario: An ancestor or descriptor is forged

- **WHEN** the deployment graph, manifest, tuple, descriptor or runtime identity is proxied, reordered or mutated
- **THEN** plan preparation fails before any stream is requested

### Requirement: Checkpoint files SHALL be verified incrementally

The system SHALL authorize one exact descriptor, enforce bounded exact-bytes
chunks, size and SHA-256, reject Git LFS pointers, and retain no payload.

#### Scenario: The stream is invalid

- **WHEN** a digest is unknown, a chunk is empty/non-bytes, a size crosses expected plus one, the digest differs, the iterator raises, or bytes form an LFS pointer
- **THEN** verification fails privately and stops without consuming a sentinel chunk

### Requirement: Checkpoint evidence SHALL be all-or-nothing and conservative

The system SHALL seal evidence only from five exact ordered receipts captured in
one authorized session.  It SHALL elevate only `checkpoint_bytes_verified` over
the inherited deployment claims.

#### Scenario: A receipt is missing, duplicated, reordered or foreign

- **WHEN** the private authority receives an invalid receipt graph
- **THEN** no evidence or public success summary is produced

### Requirement: Filesystem capture SHALL preserve one secure root view

The Linux adapter SHALL require an exact closed regular-file inventory, stream
through secure descriptors, detect path/inode/size mutation with a final sweep,
close every descriptor before sealing and fail closed on unsupported hosts.

#### Scenario: The filesystem changes during capture

- **WHEN** a file, directory or inventory entry changes after preflight or read
- **THEN** capture fails without a partial receipt or sealer call

#### Scenario: Cleanup fails

- **WHEN** any descriptor close fails
- **THEN** all remaining closes are attempted exactly once and no evidence is sealed

### Requirement: Public checkpoint summaries SHALL not disclose file identity

The canonical summary SHALL contain only evidence schema, runtime identity and
conservative flags.  It SHALL omit checkpoint paths, per-file digests, sizes and
content.

#### Scenario: Summary is requested for forged evidence

- **WHEN** evidence or any nested graph value is proxied or mutated
- **THEN** summary rendering fails privately instead of washing the mutation
