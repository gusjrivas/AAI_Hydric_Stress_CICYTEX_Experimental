# Design: descriptor-bound checkpoint byte evidence

## Authority

`prepare_laya_runtime_checkpoint_plan` accepts only an exact, deeply valid PR17
`LayaRuntimeDeploymentEvidence`.  Its ordered descriptors are derived from the
sealed `ValidatedCheckpointManifest`; callers cannot supply paths, sizes or
digests.  The five existing runtime bundle roles remain unchanged.

## Streaming core

`verify_laya_checkpoint_file_chunks` authorizes the digest before requesting a
chunk, accepts exact non-empty `bytes`, limits chunks to 1 MiB and 1,024 chunks,
stops at expected-size plus one byte, hashes incrementally and rejects Git LFS
pointers.  It retains no payload.  Iterator, hash and format errors are mapped to
private errors without chained context.

Per-file receipts bind the exact plan and descriptor.  A private capture
authority accepts exactly five ordered receipts from one adapter session.  Only
that authority can seal evidence.  The public summary exposes schemas, aggregate
runtime identity and conservative booleans; paths, file digests, sizes and bytes
remain private.

## Filesystem capture

The Linux adapter validates evidence and a canonical absolute root before I/O.
It traverses with directory file descriptors, rejects symlinks, hardlinks and
special files, and requires the exact declared directory/file inventory.  It
records descriptor fingerprints, streams every file once, repeats an exact final
path/inode/size inventory sweep, closes every descriptor exactly once, and only
then invokes the private authority and evidence sealers.  Any read, stat, sweep
or close failure prevents both sealers and leaks neither root nor content.

Windows and hosts without required descriptor capabilities fail before root
coercion or opening.  `LAYA_RUNTIME_CHECKPOINT_ROOT` is an opt-in Linux release
gate; the regular suite uses sparse invalid skeletons only for negative adapter
tests and never fabricates a successful cryptographic receipt.

## Claims

Successful evidence inherits artifact integrity plus runtime-config and
checkpoint-manifest semantics, and elevates only `checkpoint_bytes_verified`.
Lock/SBOM/OCI, origin, materialization, executor and inference claims remain
false.  The step does not establish safetensors semantics, license, provenance,
model compatibility or scientific validity.
