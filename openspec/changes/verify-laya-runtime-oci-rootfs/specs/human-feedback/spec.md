## ADDED Requirements

### Requirement: TAR receipts SHALL retain rootfs-relevant metadata

The system SHALL preserve the effective `mode`, `uid`, `gid` and `mtime` of each
real TAR entry. It SHALL preserve an exact `./` directory marker separately from
ordinary entries so root metadata is not fabricated or silently discarded.

#### Scenario: File metadata survives structural TAR validation

- **WHEN** a valid header declares non-default numeric metadata
- **THEN** its sealed entry exposes the exact effective values
- **AND** repr and errors do not disclose them

#### Scenario: Root marker metadata is preserved without becoming a normal path

- **WHEN** a valid `./` directory marker is present
- **THEN** the receipt retains its metadata as the layer root update
- **AND** `./` remains absent from the ordinary entry tuple
- **AND** conflicting repeated root markers are rejected

### Requirement: Rootfs composition SHALL bind one exact PR32 evidence graph

The system SHALL derive its plan exclusively from an exact, deeply valid
`LayaRuntimeOciTarSemanticsEvidence` and SHALL apply its ten receipts in position
order without caller-supplied overlays.

#### Scenario: A receipt graph is reordered or forged

- **WHEN** a layer is missing, duplicated, reordered, proxied or deeply mutated
- **THEN** plan preparation fails before composition
- **AND** no partial evidence is produced

### Requirement: OCI whiteouts SHALL affect only lower layers

The system SHALL treat an empty regular `.wh.<name>` as removal of the lower-layer
target subtree and `.wh..wh..opq` as hiding lower children of its directory.
Markers SHALL not appear in the final rootfs. Parent validation SHALL use lower
state plus directories declared anywhere in the current layer, but removal SHALL
still affect only lower state.

#### Scenario: A layer deletes and recreates one path

- **WHEN** the same layer contains `.wh.value` and a regular `value`
- **THEN** the lower `value` is removed
- **AND** the same-layer `value` survives regardless of TAR order

#### Scenario: An opaque directory has new children

- **WHEN** an opaque marker and new children share a layer
- **THEN** all lower children are hidden
- **AND** all current-layer children survive regardless of TAR order

#### Scenario: A same-layer directory supplies a marker parent

- **WHEN** a whiteout or opaque marker and its parent directory occur in the same layer in either TAR order
- **THEN** parent validation succeeds against the current-layer directory view
- **AND** a same-layer file or symlink in that parent position fails closed

#### Scenario: Reserved marker metadata is invalid

- **WHEN** a reserved marker is non-regular, non-empty or has link metadata
- **THEN** composition fails privately and atomically

### Requirement: The effective namespace SHALL remain root-bound

The system SHALL enforce a valid directory tree and resolve links only inside the
virtual image root. It SHALL never inspect or follow a host path.

#### Scenario: A dangling symlink remains an untraversed leaf

- **WHEN** a valid symlink target is absent and no later entry traverses it
- **THEN** the symlink remains in the composed namespace for compatibility
- **AND** this does not claim materialization or origin

#### Scenario: A later entry traverses an unsafe symlink ancestor

- **WHEN** resolution escapes the image root, is cyclic or remains dangling
- **THEN** composition fails without exposing the target

#### Scenario: A hardlink resolves against final state

- **WHEN** a forward hardlink or bounded hardlink chain ends at a regular file in the final ten-layer namespace
- **THEN** the hardlink remains valid independent of same-layer TAR order

#### Scenario: A hardlink target is invalid in final state

- **WHEN** a hardlink is missing, cyclic or does not end at an effective regular file after all layers
- **THEN** composition fails closed

### Requirement: Composition SHALL be bounded and all-or-nothing

The system SHALL cap entries at 65,536, whiteouts at 4,096, effective path/link
metadata at 8 MiB, paths at 32 components, links at 16 hops and mutations at
131,072. TAR-width maxima SHALL bound mode/uid/gid/mtime and the TAR payload cap
SHALL bound each regular node. Deleting a subtree SHALL charge each removed node.

#### Scenario: A budget is exhausted

- **WHEN** the next operation would exceed any cap
- **THEN** the operation and remaining layers are not applied
- **AND** the evidence sealer is never invoked

#### Scenario: A large subtree is removed

- **WHEN** composition removes descendants
- **THEN** a maintained parent→direct-children index supplies the bounded traversal
- **AND** every removed node consumes the remaining mutation budget

### Requirement: Rootfs evidence SHALL remain conservative and private

The system SHALL emit immutable evidence with `oci_rootfs_verified=true` only
after complete composition. It SHALL inherit all PR32 claims and elevate no other
claim. `rootfs_materialized`, origin, license, ancestry, executor and inference
SHALL remain false.

Evidence validation SHALL rederive root metadata and canonically ordered final
nodes from the exact TAR plan and SHALL recompute the private manifest commitment.

#### Scenario: Public summary is rendered

- **WHEN** exact rootfs evidence is summarized
- **THEN** the bytes contain only schemas, runtime identity and claims
- **AND** paths, targets, layer digests, metadata and the private rootfs manifest
  commitment are absent

#### Scenario: Stored evidence is deeply forged

- **WHEN** stored root metadata, nodes, bindings or manifest commitment differ from exact rederivation
- **THEN** validation and summary generation fail closed

#### Scenario: The exact real layout is composed

- **WHEN** the ten verified real layers contribute 56,996 TAR entries
- **THEN** deterministic overlay composition yields 56,114 final nodes and `oci_rootfs_verified=true`
- **AND** `rootfs_materialized=false` remains unchanged

### Requirement: Existing scientific scenarios SHALL remain isolated

The rootfs module SHALL have no productive caller in backend, scripts, runners,
readiness or dataset code.

#### Scenario: Historical and laboratory regressions run

- **WHEN** PR33 is gated
- **THEN** Melchor Romero, Pergamino, CICYTEX and mocked-sensor tests retain their
  existing behavior
- **AND** no dataset or API contract is changed

