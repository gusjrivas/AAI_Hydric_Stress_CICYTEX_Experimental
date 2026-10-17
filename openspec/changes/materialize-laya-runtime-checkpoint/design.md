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
archive ownership to container UID/GID 65532, preserving the declared host profile.

Recapture the five checkpoint files through the secure checkpoint adapter and
stream them into the NEW image under the fixed path
`/opt/laya-runtime/checkpoints/multilingual`. This mapping is supported by the
pinned `Agent` local-directory loader. Every size/digest must match the exact
issued checkpoint. Source rootfs, external checkpoint and original OCI are read
only; no HF cache is fabricated and no installation mutates those artifacts.
Checkpoint directories/files use a fixed read-only profile in the derived image.

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
Existing installation paths retain exact content/topology/mode/owner; only the
mtime of existing `dev`/`etc` directories is normalized because init-layer entries
change those parents. This is not original-OCI metadata identity. Hardlink classes
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
