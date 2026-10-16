# Human feedback runtime supply convergence

## ADDED Requirements

### Requirement: Supply convergence SHALL accept exact issued predecessors

The system SHALL accept only exact, issued and canonically valid PR22 layer,
PR35 provenance and PR36 base-ancestry evidence. It SHALL invoke each module's real
canonical validator and SHALL NOT accept shape-equivalent replacements.

The validators SHALL be exactly
`canonical_laya_runtime_oci_layer_diff_ids_summary_bytes`,
`canonical_laya_runtime_provenance_summary_bytes` and
`canonical_laya_runtime_base_ancestry_summary_bytes`.

#### Scenario: A predecessor is cloned or mutated

- **WHEN** any predecessor or nested ancestor is proxied, copied, reconstructed or changed
- **THEN** convergence fails without registering evidence

### Requirement: PR36 SHALL bind the exact PR22 input

The PR36 evidence `layer_evidence` SHALL be the same object as the PR22 predecessor
given to the combinator. Semantic similarity, equal summaries or equal digests SHALL
NOT replace identity binding.

#### Scenario: PR22 evidence is mixed across valid graphs

- **WHEN** PR36 references another individually valid PR22 instance
- **THEN** convergence fails closed

#### Scenario: PR35 is independently issued

- **WHEN** PR35 is a distinct issued graph whose rebuilt snapshot is deeply equivalent
- **THEN** its independent Python identity is accepted

### Requirement: Both bundle snapshots SHALL be canonically rebuilt

The PR22 path SHALL be
`layer_evidence.layout_evidence.plan.oci_evidence.snapshot`; the PR35 path SHALL be
`provenance_evidence.checkpoint_evidence.deployment_evidence.snapshot`. The system
SHALL rebuild both through `verify_laya_runtime_artifact_bytes`.

#### Scenario: A stored snapshot digest is recomputed after mutation

- **WHEN** stored fields look coherent but public reconstruction differs
- **THEN** convergence fails before evidence creation

### Requirement: Snapshot equivalence SHALL be deep and content-based

Rebuilt snapshots SHALL be equal in manifest, five artifact specs, five exact
contents, bindings and runtime identity. Equality SHALL NOT require the same Python
snapshot object.

#### Scenario: Separately issued snapshots contain identical content

- **WHEN** PR22 and PR35 snapshots rebuild to deeply equivalent values
- **THEN** their distinct object identities do not prevent convergence

#### Scenario: One artifact differs

- **WHEN** any manifest field, spec, byte payload, binding or runtime identity differs
- **THEN** convergence fails all-or-nothing

### Requirement: Content convergence SHALL NOT assert capture simultaneity

Successful convergence SHALL mean only that both authority chains describe the
same canonical bundle content and runtime identity. It SHALL NOT assert co-temporal
capture, same filesystem root, same host, same checkout or same session.

#### Scenario: Capture context is requested

- **WHEN** converged evidence is summarized
- **THEN** no time, root, host, checkout or session relationship is claimed

### Requirement: Evidence authority SHALL be module-side and concurrent

The system SHALL register exact evidence identity and deep semantics under a private
module lock. It SHALL reject clones and post-issuance mutation without using a
global one-shot or caller-controlled authority.

#### Scenario: Two valid combinations run concurrently

- **WHEN** independent calls use valid issued predecessors
- **THEN** both may succeed without consuming shared global state

#### Scenario: Valid predecessors are mixed

- **WHEN** PR36 does not reference the exact PR22, or PR35 content/runtime identity differs
- **THEN** identity or deep snapshot convergence rejects the mix

### Requirement: Registry cleanup SHALL be weak and identity-safe

Registry entries SHALL use weakrefs, validate liveness under lock and remove an
entry only when its cleanup callback still matches the current weakref and object
identity. Before conditional removal, the callback SHALL clear only its expired
record with `record.semantics = ()`. It SHALL NOT alter a replacement record.

#### Scenario: Evidence is garbage-collected

- **WHEN** the issued evidence loses all strong external references
- **THEN** weak cleanup removes only its matching registry record

#### Scenario: A stale callback runs after id reuse

- **WHEN** a later live entry occupies the same numeric identity slot
- **THEN** the old record releases its semantics and callback mismatch preserves the complete later entry

#### Scenario: Expired record does not retain its ancestor graph

- **GIVEN** a test retains `expired_record` while a live replacement exists
- **WHEN** evidence and predecessors are deleted and garbage collection runs
- **THEN** its reference is `None`, `semantics` retains no ancestors, graph weakrefs are `None`, and registry returns to baseline while replacement survives

#### Scenario: A dead record is queried

- **WHEN** liveness validation finds an expired weakref
- **THEN** summary fails closed instead of trusting stale semantics

### Requirement: Convergence SHALL elevate one new claim only

The only new true claim SHALL be
`runtime_supply_content_convergence_verified`. Existing predecessor claims retain
their original meanings and SHALL NOT be promoted by convergence.

#### Scenario: Exact convergence succeeds

- **WHEN** all issued bindings and rebuilt snapshots converge
- **THEN** `runtime_supply_content_convergence_verified=true`

### Requirement: True predecessor claims SHALL be exact

The evidence SHALL preserve the eleven PR22 true claims, add PR36
`base_ancestry_verified`, preserve the eight additional PR35 true claims, and add
only `runtime_supply_content_convergence_verified`.

#### Scenario: A true claim is missing or added

- **WHEN** the evidence differs from the exact 21-claim true matrix
- **THEN** evidence creation and summary fail closed

### Requirement: Operational and external claims SHALL remain false

Lock, SBOM, rootfs, TAR, origin, license, recipe, build, reproducibility,
materialization, executor and inference claims SHALL remain false after convergence.

#### Scenario: Converged supply is summarized

- **WHEN** convergence evidence is valid
- **THEN** `lock_verified`, `sbom_verified`, `lock_sbom_consistent`, `oci_rootfs_verified` and `tar_semantics_verified` are false
- **AND** origin, license, recipe/build/reproducibility, materialization, executor and inference flags are false

### Requirement: Existing cardinalities SHALL converge without new caps

The combinator SHALL require 3 predecessors, 5 bundle artifacts, 5 checkpoint files,
10 PR22 layers, 16 PR35 provenance objects and 4 PR36 base-prefix positions. It
SHALL introduce no parsing, streaming or graph cap beyond predecessor contracts.

#### Scenario: A cardinality differs

- **WHEN** any 3/5/5/10/16/4 collection is missing, extra or reordered
- **THEN** convergence fails before evidence registration

### Requirement: The public surface SHALL be closed

The module SHALL expose only `LayaRuntimeSupplyConvergenceEvidence`,
`verify_laya_runtime_supply_convergence` and
`canonical_laya_runtime_supply_convergence_summary_bytes`.

#### Scenario: Public exports are inspected

- **WHEN** the module API is enumerated
- **THEN** helpers, registries, locks, predecessor modules and factory capabilities remain private

### Requirement: Public summaries SHALL use one exact minimal allowlist

The canonical summary SHALL contain exactly `schema_version`, predecessor schema
keys `layer_evidence_schema_version`, `provenance_evidence_schema_version` and
`base_ancestry_evidence_schema_version`, `runtime_identity_schema_version`,
`runtime_identity_sha256` and the complete boolean matrix. No extra key is allowed.

#### Scenario: Summary keys are enumerated

- **WHEN** valid evidence is summarized
- **THEN** the six non-boolean keys and complete boolean matrix are present once
- **AND** artifact bytes, paths, manifests, internal digests, sizes, receipts, layers and capture context are absent

### Requirement: Positive tests SHALL retain real predecessor authority

Positive tests SHALL keep all three canonical validators unmodified and SHALL emit
legitimate PR22 ancestry containing a reconstructible real snapshot. A helper that
omits `layout_evidence.plan.oci_evidence.snapshot` SHALL NOT satisfy the positive path.

#### Scenario: A positive test replaces authority

- **WHEN** a canonical validator is monkeypatched or PR22 lacks its real snapshot path
- **THEN** the test setup is invalid and cannot demonstrate convergence

#### Scenario: Evidence is summarized after ancestor mutation

- **WHEN** any registered predecessor or nested snapshot changed after issuance
- **THEN** summary generation fails without disclosing the changed value

### Requirement: The combinator SHALL remain pure and isolated

The module SHALL perform no filesystem, network, subprocess or adapter operation,
create no fixture and have no productive caller. Existing scientific and operational
flows SHALL remain unchanged.

#### Scenario: Existing scenarios run

- **WHEN** Melchor Romero, Pergamino, CICYTEX or mocked-sensor flows execute
- **THEN** they do not import or invoke supply convergence

### Requirement: Cross-platform CI SHALL follow GREEN

A later focal CI job SHALL run on Linux and Windows only after RED A–D and GREEN.
It SHALL include base-ancestry and provenance dependencies without external capture
or new fixtures.

#### Scenario: GREEN is not complete

- **WHEN** any RED group remains unsatisfied
- **THEN** the PR37 CI job is not treated as a completed gate
