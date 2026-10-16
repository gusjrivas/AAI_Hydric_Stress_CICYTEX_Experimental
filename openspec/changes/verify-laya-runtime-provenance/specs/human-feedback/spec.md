# Human feedback runtime provenance verification

## ADDED Requirements

### Requirement: Git objects SHALL have dual content authority

The system SHALL accept only bounded raw Git objects whose type, declared size and
Git SHA-1 match the pinned object identity and whose exact bytes match an independent
lowercase SHA-256 authority.

#### Scenario: Either authority differs

- **WHEN** framing, type, size, SHA-1 or SHA-256 differs from its authority
- **THEN** validation fails before the object participates in a DAG

### Requirement: Source provenance SHALL bind the pinned release DAG

The system SHALL bind exact source commit
`68804629e8ccd9d616d48a40e87de9fabbeae069` to annotated unsigned tag `v0.4.2`
and to the exact tree-selected `LICENSE` and `pyproject.toml` blobs.

#### Scenario: Source graph is exact

- **WHEN** tag, commit, trees and declaration blobs match both content authorities and exact DAG links
- **THEN** the narrow source Git content flag may become true
- **AND** the unsigned tag does not establish authenticity or origin

#### Scenario: Source graph is mixed

- **WHEN** any valid object comes from another commit, tag, tree or authority set
- **THEN** source evidence fails closed

### Requirement: Source license declarations SHALL remain non-legal metadata

The system SHALL recognize the expected Apache text in exact `LICENSE` bytes and
the Apache declaration in exact `pyproject.toml` bytes.  The resulting declaration
flag SHALL NOT mean `license_verified` or a legal license conclusion.

#### Scenario: Both source declarations are observed

- **WHEN** both selected blobs contain their exact expected declarations
- **THEN** `source_license_declaration_observed` may become true
- **AND** `license_verified` remains false

### Requirement: Checkpoint provenance SHALL bind one exact tree

The system SHALL bind checkpoint commit
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` to its exact `multilingual` tree,
five contractual paths and exact tree-selected README Apache metadata.

#### Scenario: Checkpoint tree is exact

- **WHEN** commit, trees, five selected blobs and README match both authorities and exact DAG links
- **THEN** the narrow checkpoint Git content flag may become true

#### Scenario: Tree content is incomplete or foreign

- **WHEN** a selected path is missing, duplicated, extra, unreachable or from another authority set
- **THEN** checkpoint provenance fails closed without partial evidence

### Requirement: LFS pointers SHALL be links rather than payload evidence

The system SHALL classify each selected checkpoint blob as an exact small blob or
a canonical Git LFS pointer.  Pointer oid and size SHALL bind the matching PR34
descriptor but SHALL NOT independently prove checkpoint payload bytes.

#### Scenario: A canonical pointer matches PR34

- **WHEN** its oid and size equal the corresponding exact PR34 descriptor
- **THEN** the Git link may participate in checkpoint provenance
- **AND** `checkpoint_bytes_verified` is inherited solely from PR34 evidence

#### Scenario: Pointer and descriptor differ

- **WHEN** oid, size, role, path, revision or runtime identity differs
- **THEN** no provenance evidence is sealed

### Requirement: Checkpoint Apache metadata SHALL remain a declaration

The system SHALL recognize expected Apache metadata only in the exact README blob
selected by the checkpoint DAG.  The declaration SHALL NOT prove license validity,
coverage, compatibility or permission to use checkpoint payloads.

#### Scenario: README declaration is observed

- **WHEN** exact README bytes contain the expected Apache metadata
- **THEN** `checkpoint_license_declaration_observed` may become true
- **AND** `license_verified` remains false

#### Scenario: README omits repository identity

- **WHEN** real README frontmatter declares Apache metadata but no repository or subfolder
- **THEN** identity derives from the plan, pinned DAG edges and exact PR34 evidence

### Requirement: Provenance validation SHALL be bounded and all-or-nothing

The system SHALL cap inputs at 16 objects, 64 KiB per object, 1 MiB aggregate,
256 entries per tree, eight path components and 64 DAG visits.  Missing, duplicate,
extra, oversized, malformed or unreachable objects SHALL fail before sealing.

#### Scenario: A bound is exhausted

- **WHEN** the next object, tree entry, path component or DAG visit exceeds a cap
- **THEN** validation stops without partial evidence or summary

### Requirement: Provenance evidence SHALL reject mixed authorities

The system SHALL require one coherent source set, checkpoint set, runtime identity
and exact PR34 evidence.  It SHALL canonically rebuild all bindings before emitting
immutable evidence or a public summary.

#### Scenario: Individually valid inputs are mixed

- **WHEN** objects or PR34 evidence belong to different revisions, manifests or runtime identities
- **THEN** validation and summary generation fail closed

#### Scenario: A checkpoint edge is mismatched

- **WHEN** a DAG edge, role, path, Git object, small-blob digest or LFS oid/size differs from exact PR34 bindings
- **THEN** no receipt set or provenance evidence is accepted

### Requirement: Provenance summaries SHALL remain private and conservative

The public summary SHALL expose only schemas, runtime identity, content flags and
`source_license_declaration_observed` or
`checkpoint_license_declaration_observed`.  Object bytes, Git identifiers, SHA
authorities, paths, LFS data and license text SHALL remain private.

#### Scenario: Valid provenance is summarized

- **WHEN** exact evidence is rendered
- **THEN** `origin_verified`, `license_verified`, base ancestry and `runtime_materialized` remain false
- **AND** `executor_available` and `inference_executed` remain false

### Requirement: The provenance core SHALL remain pure and isolated

The core SHALL consume bytes only and SHALL perform no filesystem, Git process,
network, clone, fetch, download, materialization, model load or inference.  Backend,
runners, readiness and scripts SHALL have no productive caller.

#### Scenario: Normal suites run

- **WHEN** synthetic bounded provenance tests and existing scientific scenarios execute
- **THEN** no external repository or checkpoint is accessed

#### Scenario: The public API is inspected

- **WHEN** callers import the provenance module
- **THEN** the only public operations are `prepare_laya_runtime_provenance_plan`, `verify_laya_runtime_provenance_objects` and `canonical_laya_runtime_provenance_summary_bytes`

### Requirement: Real provenance evidence SHALL require an opt-in gate

A real release gate MAY validate pre-captured objects for both pinned repositories
with exact PR34 evidence.  It SHALL be opt-in, non-downloading and separate from
ordinary CI; absence of that gate SHALL NOT be reported as real verification.

Its helper SHALL precheck each local object, invoke only bounded `git cat-file`, set
`GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1` and `GIT_TERMINAL_PROMPT=0`, and
enforce a fixed subprocess timeout.

#### Scenario: The real gate is not configured

- **WHEN** normal CI or local tests run without external captured inputs
- **THEN** they exercise only synthetic contracts and publish no real provenance claim

#### Scenario: A local object is absent

- **WHEN** precheck cannot prove a required object exists locally
- **THEN** the helper fails without lazy fetch, replacement lookup or terminal prompt

