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
README Apache metadata is also observed from its exact tree-selected blob.

PR34 `LayaRuntimeCheckpointEvidence` is the only authority that the five payloads
match their sizes and SHA-256 digests.  PR35 neither accepts replacement file
receipts nor re-hashes payloads.  It rejects a checkpoint DAG, pointer or descriptor
that does not bind exactly to the same runtime identity, revision and five-file
manifest proven by PR34.

## Bounded validation and canonical evidence

Public fixed positive caps limit object count, individual and aggregate bytes,
tree entries, path components and DAG visits.  Git object framing, type and size
are checked before parsing.  Trees must be canonical, paths unique and the selected
commit/tag/tree/blob relationships exact.  LFS pointers use a closed grammar and
declared sizes must be within the checkpoint descriptor bounds.

All inputs are consumed all-or-nothing.  Missing, duplicate, extra, oversized,
foreign or unreachable objects fail closed.  Source and checkpoint authority sets,
PR34 evidence and runtime identity cannot be mixed across revisions.  Exact-class,
immutable evidence is canonically rebuilt from validated content before summary.

## Claims and privacy

Successful evidence may elevate only narrow flags for verified source Git content,
verified checkpoint Git content and observed source/checkpoint license declarations.
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
object packets and do not clone, fetch or download.  A separate opt-in release gate
may validate pre-captured objects from the two real pinned repositories plus real
PR34 evidence.  Its result is external release evidence, not a mandatory CI claim,
and it does not broaden the pure core or authorize materialization.

## TDD sequence

RED first specifies Git framing, dual digests, exact DAG links, source declarations,
checkpoint tree/LFS links, PR34 binding, caps, privacy, mix-and-match rejection and
conservative flags.  GREEN will implement only the pure validator.  A later slice
may design secure capture; origin attestation, legal review and execution require
separate contracts.

