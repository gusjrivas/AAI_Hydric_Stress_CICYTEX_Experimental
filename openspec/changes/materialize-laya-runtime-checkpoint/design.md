# Offline derived-runtime materialization

## Authority

The pure plan binds an exact live issued PR39 materialization evidence instance
and the exact issued checkpoint instance reachable through
`rootfs._plan._supply_evidence._provenance_evidence.checkpoint_evidence`.
Both are deeply revalidated and share the same runtime identity schema/digest;
equivalent independently captured snapshot objects need not be identical. Clones,
mixed snapshots, rebinding, revoked parents and altered commitments fail before I/O.
The evidence inherits all 35 predecessor claims, changing only
`runtime_materialized=false` to true. Public summaries omit paths, text, image and
container IDs, nonces and private commitments.

## Source and installation

Acquire a descriptor-bound lease that serializes against PR39 disposal. Export
only its exact verified tree using descriptor-relative traversal, never following
symlinks. Stream regular contents and rederive the PR39 commitment. Normalize
archive ownership to container UID/GID 65532, preserving the declared host profile,
except for the explicit Engine-managed file projection below.
Prefer one-header USTAR prefix/name encoding. Use GNU longname/longlink only when
USTAR cannot represent an entry; never introduce PAX. Preflight the physical
header count, including GNU metadata headers but not their payload blocks, against
the parser's unchanged 65,536-header limit before writing the first archive byte.
Paths/link targets remain limited to 4,096 UTF-8 bytes. The real rootfs has 56,114
nodes; GNU-only encoding needs 68,163 headers, while the preferred encoding needs
56,118 before checkpoint additions. Logical node count alone is not a TAR budget.

Recapture the five checkpoint files through the secure checkpoint adapter and
stream them into the NEW image under the fixed path
`/opt/laya-runtime/checkpoints/multilingual`. This mapping is supported by the
pinned `Agent` local-directory loader. Every size/digest must match the exact
issued checkpoint. Source rootfs, external checkpoint and original OCI are read
only; no HF cache is fabricated and no installation mutates those artifacts.
Checkpoint directories/files use a fixed read-only profile in the derived image.

The authenticated input is verified completely, but the NEW derived image applies
one closed projection for `etc/hosts`, `etc/hostname` and `etc/resolv.conf`.
Docker replaces these paths in its init layer even when they existed in the image.
Do not silently exclude original entries from the expected recapture manifest.
Instead, project these image entries to empty regular files, root:root, mode
0755 and mtime zero. The expected installation manifest includes their exact
projected bytes and metadata, including placeholders for absent source entries.
Read-only inspection of the pinned ten-layer OCI found regular `etc/hostname`
and `etc/resolv.conf` entries and no `etc/hosts` entry or matching whiteout; the
derived image therefore adds the third placeholder rather than inventing source
bytes. All three projected entries must be present in the expected manifest.
Source bytes are still descriptor-read, rehashed
and covered by the original rootfs commitment; the source tree is never changed.
Symlink/hardlink collisions or aliases are refused, not projected. Recapture
normalizes only the Engine-generated mtime of these exact placeholders and must
otherwise verify every byte of the declared projection plus five checkpoints.
This is deliberately not byte identity with the original OCI rootfs.

## Trusted orchestration and isolated child

The local Docker endpoint is an explicit trusted dependency. Sanitize inherited
Docker context/environment; never select a remote daemon or artifact-supplied
command. Use closed argv with `shell=False`, bounded streams, hard timeout and
owned cleanup records. No pull, build network, package resolution or download is
permitted during materialization. The artifact is a NEW derived image, not the
original OCI manifest identity or an attested/reproducible upstream build.

Inspect image and container configuration before starting. Require UID/GID 65532,
read-only rootfs, network none, ALL capabilities dropped, no-new-privileges,
effective seccomp, no privileged mode, host bind/socket/device/port exposure, and
fixed pids/memory/swap/cpu/FD/output/time limits. Bounded private tmpfs is permitted
for temporary/cache paths. Nested user namespaces are unavailable on the current
runner; Docker isolation does not claim resistance to a compromised daemon/kernel.

Independently recapture the stopped container's filesystem with trusted host code
and verify the expected normalized rootfs plus checkpoint additions. Child Python
output cannot establish content identity. Then run a fixed probe using the image's
Python/loader/libraries, not the host interpreter. Require Python 3.11.10, Laya
0.4.2, CPU, exact local model registration and successful strict safetensors load.
`build_router().load("multilingual")` is the pinned API; do not call inference.
Set local-model and five-digest mappings plus closed offline/cache environment.
Tokenizer config repair must be a no-op; content drift or attempted rootfs write
aborts. Output is a closed non-private JSON observation, not scientific evidence.

The stopped-container export has an explicit init-layer profile independently
observed against Docker 29.5.2. Only when absent from the authenticated installation,
allow empty root-owned mode-0755 `.dockerenv`, `dev/console` and
`etc/{hosts,hostname,resolv.conf}`; root-owned mode-0755 directories
`dev/pts`, `dev/shm`, `dev`, `proc`, `sys`; and mode-0777 root-owned symlink
`etc/mtab -> /proc/mounts`. No nonempty payload or other extra path is accepted.
Existing installation paths retain exact projected content/topology/mode/owner;
only the mtime of existing `dev`/`etc` directories and the three exact declared
placeholders is normalized because Docker recreates those paths. This is not
original-OCI metadata identity. Hardlink classes
are compared independently of which equivalent inode member Docker exports first.
Daemon logs use an inspected fixed 64-KiB/one-file rotation policy.

## Lifecycle and failure

Only seal after the independent recapture and successful load probe. Retain the
owned image while runtime evidence is live. Container/image IDs and ownership
nonce labels must match before cleanup; never prune global resources. Explicit
disposal revokes authority and removes only owned objects, with retry after
transient cleanup failure. Rootfs lease and external source descriptors always
close. A failed probe, timeout, OOM, unavailable restriction, missing/mutated source
or cleanup error never produces runtime authority. Orphans are not adopted.

Import/create intents record exact fresh image references/container names before
mutation. Lost replies are reconciled only by those references plus ownership nonce
and closed profile, never by global listing. A failed attempt whose cleanup also
fails raises a private issued error handle with `cleanup_pending`; the caller can
retry cleanup without receiving runtime authority. Dropping an error/evidence
without explicit cleanup can leave an orphan; GC never silently deletes external
resources. Source leases use per-resource conditions, so one long load cannot block
independent rootfs leases/disposals. Same-thread disposal during a lease is refused.

## Progression

First implement pure contracts, then resource leases, bounded artifact assembly,
Docker state machine and independent recapture, then synthetic and real probes.
Runtime executability for a closed load probe does not create the governed
executor of PR41. No productive backend/UI/runner wiring is introduced.

## Real-gate findings

Real immutable checkpoint capture exposed legal short filesystem reads exhausting
the predecessor's 1,024-chunk budget. Coalesce raw reads into logical chunks of at
most 1 MiB, preserving the original byte/count limits, exact SHA/size checks and
one overflow-detection byte. This fixes the filesystem boundary, not the pure
verification contract. Both this and the physical TAR-header correction have
separately reproduced RED regressions before implementation.

The complete real gate at executable `fedbbca` failed after import and stopped
probe creation; it did not emit runtime authority and cleanup had no pending
handle. Minimal independent Docker reproductions demonstrated replacement of
the three Engine-managed files and refuted physical-header/PAX expansion as the
cause. The correction must follow RED/GREEN and a fresh complete real gate; the
previous CI 16/16 at `b819db7` is not acceptance of changed executable code.
