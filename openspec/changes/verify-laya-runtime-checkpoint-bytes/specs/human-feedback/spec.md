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

### Requirement: Filesystem capture SHALL bind the exact checkpoint root

The Linux adapter SHALL reject filesystem root `/` before any open.  The supplied
checkpoint root SHALL denote the exact contents of the checkpoint manifest's
`multilingual` subfolder: the five declared files and their declared intermediate
directories are immediate descendants of that root, not descendants of an
additional `multilingual/` directory.  The adapter SHALL require that exact closed
regular-file inventory and inspect only the bounded declared adjacency/depth.  Root
preflight SHALL coerce a path-like value exactly once, normalize every coercion
failure to a private capture error, and reject more than 128 absolute path
components before opening any descriptor.

#### Scenario: Root scope is unsafe or ambiguous

- **WHEN** root is `/`, points above the manifest `multilingual` contents, contains an unexpected adjacent directory, or exceeds the declared inventory depth/count
- **THEN** capture fails before opening `/` as a capture root or recursively descending into the unexpected subtree

#### Scenario: Root coercion is hostile or over the component cap

- **WHEN** `__fspath__` raises or a canonical absolute root has more than 128 components
- **THEN** capture fails privately after at most one coercion, before any filesystem open, without leaking the original exception

### Requirement: Filesystem capture SHALL preserve one secure root view

The Linux adapter SHALL stream through secure descriptors, detect replacement of
the supplied root path or any ancestor in addition to descriptor-local
path/inode/size mutation, close every descriptor before sealing and fail closed on
unsupported hosts.

#### Scenario: The filesystem changes during capture

- **WHEN** a file, directory or inventory entry changes after preflight or read
- **THEN** capture fails without a partial receipt or sealer call

#### Scenario: Cleanup fails

- **WHEN** any descriptor close fails, including the final retained-root close after receipts and the final sweep
- **THEN** all remaining closes are attempted exactly once and no evidence is sealed

#### Scenario: A filesystem primitive fails

- **WHEN** open, adjacency scan, entry stat, descriptor fstat, read or close fails at any capture phase
- **THEN** capture fails privately and neither authority nor evidence is sealed

### Requirement: Public checkpoint summaries SHALL not disclose file identity

The canonical summary SHALL contain only evidence schema, runtime identity and
conservative flags.  It SHALL omit checkpoint paths, per-file digests, sizes and
content.

#### Scenario: Summary is requested for forged evidence

- **WHEN** evidence or any nested graph value is proxied or mutated
- **THEN** summary rendering fails privately instead of washing the mutation
