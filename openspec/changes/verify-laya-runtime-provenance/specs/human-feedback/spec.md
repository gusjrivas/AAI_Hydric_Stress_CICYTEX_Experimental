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

### Requirement: PR34 authority SHALL require verified issuance

PR35 SHALL accept only checkpoint plans, receipts, capture authority and evidence
issued by PR34's verified streaming path and private sealers.  Matching classes,
fields, slots, shapes or recomputed digests alone SHALL convey no authority.

#### Scenario: A checkpoint graph is cloned structurally

- **WHEN** `object.__new__`, copied fields/slots or a shape-only wrapper forges any PR34 node
- **THEN** canonical checkpoint summary and provenance plan preparation fail
- **AND** no provenance object chunk is consumed

### Requirement: PR34 issuance SHALL be narrowly hardened

The checkpoint module SHALL retain private issuance evidence across plan, receipts,
capture authority and final evidence.  This dependency hardening SHALL add no new
payload, origin, license, materialization, executor or inference claim.

#### Scenario: Structure matches without issuance

- **WHEN** all visible PR34 values match but the private issuance chain is absent
- **THEN** checkpoint and provenance validation fail closed

### Requirement: The module registry SHALL be the sole checkpoint authority

PR34 SHALL authorize graphs only through its private module registry with strong
identity and topology bindings.  `_semantic_capability` SHALL be a non-authoritative
caller mirror; weak cleanup SHALL only remove unreachable registry state.

#### Scenario: The caller mirror is mutated

- **WHEN** `_semantic_capability` is copied, replaced or deleted on an issued or forged object
- **THEN** registry authority is neither granted nor revoked by that mirror mutation

#### Scenario: An issued graph is cloned

- **WHEN** a clone reproduces every field and topology but has different object identities
- **THEN** canonical checkpoint summary and provenance preparation reject the clone

### Requirement: Registry graph validation SHALL have exact budgets

Registry validation SHALL cap graph nodes/items at 2,048, aggregate semantic content
at 16 MiB and nesting depth at 64.  It SHALL fail closed before traversing or
encoding beyond any live remaining budget.

#### Scenario: Topology or content exceeds a cap

- **WHEN** the next node, item, semantic byte or nesting level exceeds its budget
- **THEN** checkpoint summary and provenance preparation fail without object consumption

### Requirement: Strings and keys SHALL be prechecked before UTF-8

Before encoding semantic content, validation SHALL check string character lengths,
mapping cardinality and key shape against remaining node/item and aggregate limits.
Unbounded caller text SHALL NOT be encoded merely to discover it exceeds a cap.

#### Scenario: A forged graph contains an oversized key

- **WHEN** key shape or character length already exceeds the remaining budget
- **THEN** validation fails before requesting its UTF-8 representation

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

### Requirement: Streaming caps SHALL be live and coherent

The chunk-byte cap SHALL be positive and no greater than the object-byte cap.
Validation SHALL consult live public caps, including test-lowered values, for every
object and aggregate decision.

#### Scenario: A live cap is lowered

- **WHEN** a chunk, object or aggregate exceeds the current public cap
- **THEN** verification fails before accepting excess bytes

### Requirement: Chunk structures SHALL pass complete preflight

Before consuming any chunk container, the verifier SHALL validate the whole outer
collection, exact order/count, every item shape and identity, and every container
type.  A malformed later entry SHALL consume no earlier stream.

#### Scenario: The last chunk container is invalid

- **WHEN** every earlier entry is valid but the final container has the wrong structure
- **THEN** verification fails with zero chunks requested from every entry

### Requirement: Roles SHALL determine repository and Git kind

The plan SHALL derive repository and kind from a closed role matrix.  Tags, commits,
trees and blobs SHALL occupy only their prescribed roles, and every caller-visible
derived field SHALL equal the canonical object profile.

#### Scenario: A derived field is forged

- **WHEN** role, repository, kind, object identity, digest or size differs from its canonical matrix row
- **THEN** plan, envelope and receipt validation fail closed

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

### Requirement: Factory authority SHALL remain private and exact-class

Envelope, receipt and evidence sealing SHALL retain a private factory capability.
It SHALL reject subclasses, proxies, uninitialized objects and reconstructed values
without ever exposing or lending that capability to a caller.

#### Scenario: A nested value is forged

- **WHEN** an envelope, receipt or evidence graph contains a non-exact or factory-less value
- **THEN** unit verification and summary fail without sealing replacement evidence

### Requirement: Unit verification SHALL revalidate PR34 ancestry

`verify_laya_runtime_provenance_objects` SHALL deeply validate the exact PR34
checkpoint evidence, deployment graph, runtime identity, five descriptors and
bindings plus the issued plan/receipt/capture chain before stream preflight and
again before provenance sealing.

#### Scenario: A shallow checkpoint wrapper recomputes its digest

- **WHEN** any PR34 ancestor or nested binding is forged despite matching surface fields
- **THEN** no chunk is consumed and no provenance evidence is produced

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

#### Scenario: Public exports are inspected

- **WHEN** `__all__` is evaluated
- **THEN** it contains only intended constants, five public dataclasses and the three public operations
- **AND** imports, parsers, stream helpers, factory capability and sealers remain private

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
