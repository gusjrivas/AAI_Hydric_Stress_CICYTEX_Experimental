# Design: bounded content-addressed provenance evidence

## Trust boundary

The core receives bytes and immutable authority records only.  It does not open a
repository, invoke Git, access a filesystem or use the network.  The caller must
provide every required commit, annotated tag, tree and declaration blob together
with its pinned Git SHA-1 and independent lowercase SHA-256.

Git SHA-1 is used only as the repository object identity required to traverse the
pinned DAG.  SHA-256 binds the exact supplied object bytes independently.  Both
must match before an object can participate; neither establishes who produced or
published it.

The only public operations are `prepare_laya_runtime_provenance_plan`,
`verify_laya_runtime_provenance_objects` and
`canonical_laya_runtime_provenance_summary_bytes`.  Object parsers, per-object
stream verification and evidence sealing remain private implementation details.

`__all__` is closed to those functions; the five dataclasses
`LayaGitObjectSpec`, `LayaRuntimeProvenancePlan`, `LayaGitObjectEnvelope`,
`VerifiedLayaProvenanceObject` and `LayaRuntimeProvenanceEvidence`; and exactly
these constants:

- `PROVENANCE_PLAN_SCHEMA`, `PROVENANCE_EVIDENCE_SCHEMA`;
- `SOURCE_REPOSITORY`, `CHECKPOINT_REPOSITORY`, `SOURCE_COMMIT`,
  `CHECKPOINT_COMMIT`, `PROVENANCE_OBJECTS`;
- `MAX_PROVENANCE_OBJECTS`, `MAX_PROVENANCE_OBJECT_BYTES`,
  `MAX_PROVENANCE_TOTAL_BYTES`, `MAX_PROVENANCE_CHUNK_BYTES`,
  `MAX_PROVENANCE_CHUNKS`, `MAX_PROVENANCE_TREE_ENTRIES`,
  `MAX_PROVENANCE_PATH_COMPONENTS`, `MAX_PROVENANCE_DAG_VISITS`.

Imported names and all underscore helpers remain private.

## Source profile

The source side is fixed to `NandhaKishorM/laya` commit
`68804629e8ccd9d616d48a40e87de9fabbeae069` and annotated tag `v0.4.2`.  The tag
is intentionally recorded as unsigned.  The verified commit/tree path must select
the exact `LICENSE` and `pyproject.toml` blobs.  The core observes the expected
Apache license text and the project metadata declaration; it does not make a legal
license determination.

## Checkpoint profile and PR34 authority

The checkpoint side is fixed to `convaiinnovations/laya` commit
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`.  Its Git DAG must select the exact
`multilingual` tree and the five PR17 paths: `encoder/config.json`,
`model.safetensors`, `rl_agent_config.json`, `tokenizer/tokenizer.json` and
`tokenizer/tokenizer_config.json`.

Each selected blob is classified as either an exact small Git blob or a canonical
Git LFS pointer.  For LFS, the pointer only links an oid/size declaration to the
corresponding PR34 descriptor; it is not the checkpoint payload.  The checkpoint
README Apache metadata is also observed from its exact tree-selected blob.  The
real README frontmatter does not carry repository or subfolder identity; those
bindings derive only from the plan, pinned DAG edges and exact PR34 evidence.

PR34 `LayaRuntimeCheckpointEvidence` is the only authority that the five payloads
match their sizes and SHA-256 digests.  PR35 neither accepts replacement file
receipts nor re-hashes payloads.  It rejects a checkpoint DAG, pointer or descriptor
that does not bind exactly to the same runtime identity, revision and five-file
manifest proven by PR34.

## Bounded validation and canonical evidence

The fixed caps are 16 objects, 64 KiB per object, 1 MiB aggregate object bytes,
256 entries per tree, eight path components and 64 DAG visits.  The live chunk cap
must be positive and no larger than the 64 KiB object cap; chunk count remains
bounded.  Tests may lower public caps and validation must consult the live values.

Before consuming any chunk iterator, the verifier validates the complete outer
collection, exact order and count, every item shape/object identity and every chunk
container type.  A malformed later container therefore consumes no earlier stream.
Only after preflight may bounded incremental hashing begin.

Git object framing, type and size are checked before parsing.  Trees must be
canonical, paths unique and selected commit/tag/tree/blob relationships exact.
LFS pointers use a closed grammar and declared sizes must equal their checkpoint
descriptor bounds.

Role determines repository and kind.  The closed kind matrix is:

- tag: `source_tag`;
- commit: `source_commit`, `checkpoint_commit`;
- tree: `source_tree`, `checkpoint_tree`, `multilingual_tree`, `encoder_tree`,
  `tokenizer_tree`;
- blob: `source_license`, `source_pyproject`, `checkpoint_readme`,
  `encoder_config`, `weights_lfs`, `laya_config`, `tokenizer_lfs`,
  `tokenizer_config`.

The five `source_*` roles derive `SOURCE_REPOSITORY`; every remaining role derives
`CHECKPOINT_REPOSITORY`.  Caller-supplied repository, kind, SHA-1, SHA-256 and size
must equal the canonical profile row exactly.

All inputs are consumed all-or-nothing.  Missing, duplicate, extra, oversized,
foreign or unreachable objects fail closed.  Source and checkpoint authority sets,
PR34 evidence and runtime identity cannot be mixed across revisions.  Exact-class,
immutable evidence is canonically rebuilt from validated content before summary.

Envelope, receipt and evidence constructors require a private factory capability
that is never exported or passed to callers.  Exact-class checks reject subclasses,
proxies and `object.__new__` forgeries.  The unit object-set verifier deeply
revalidates the full PR34 checkpoint ancestry before preflight and again before
sealing; a recomputed shallow wrapper cannot lend authority.

## Claims and privacy

Successful evidence may elevate only `provenance_objects_verified`,
`source_git_content_verified`, `checkpoint_git_content_verified`,
`source_license_declaration_observed` and
`checkpoint_license_declaration_observed` beyond exact inherited PR34 claims.
“Content verified” means exact supplied object bytes match both authorities and the
pinned DAG.  “Declaration observed” means expected metadata exists in exact selected
blobs; it is not legal advice or a license grant.

`checkpoint_bytes_verified=true` is inherited only from exact PR34 evidence.
`origin_verified`, `license_verified`, base ancestry, `runtime_materialized`,
`executor_available` and `inference_executed` remain false.  An unsigned tag cannot
raise authenticity or origin claims.

The public summary contains only schemas, runtime identity and conservative flags.
Git object bytes, commit/tree/blob identifiers, SHA authorities, paths, LFS data and
license text remain absent from repr, errors and summary.

## Isolation and real gate

No adapter or productive caller is introduced.  Normal tests use bounded synthetic
object packets and do not clone, fetch or download.  A release-test helper may read
only pre-existing local objects using `git cat-file`, after an explicit local object
precheck.  Every Git subprocess sets `GIT_NO_LAZY_FETCH=1`,
`GIT_NO_REPLACE_OBJECTS=1` and `GIT_TERMINAL_PROMPT=0`, and has a fixed timeout.

The separate opt-in gate may validate those local objects from the two real pinned
repositories plus real PR34 evidence.  It must not fetch missing objects.  Its
result is external release evidence, not a mandatory CI claim, and it does not
broaden the pure core or authorize materialization.

## TDD sequence

RED first specifies Git framing, dual digests, exact DAG links, source declarations,
checkpoint tree/LFS links, PR34 binding, caps, privacy, mix-and-match rejection and
conservative flags.  GREEN will implement only the pure validator.  A later slice
may design secure capture; origin attestation, legal review and execution require
separate contracts.

