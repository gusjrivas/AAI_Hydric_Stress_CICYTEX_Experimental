# Design: Pure OCI rootfs composition

## Boundary

The compositor accepts only an exact, deeply valid
`LayaRuntimeOciTarSemanticsEvidence`. It never accepts caller-supplied layers,
entries, whiteouts, paths or budgets and performs no I/O. The ten sealed receipts
are applied in their existing positions from layer 0 through layer 9.

## Metadata closure

`LayaOciTarEntry` retains effective `mode`, `uid`, `gid` and `mtime`. An exact
`./` directory marker remains excluded from ordinary entries but is retained as
optional root-directory metadata on its layer receipt. Repeated identical root
markers are harmless; conflicting root metadata in one TAR is rejected.

Numeric metadata is closed by the TAR-width public maxima for mode, uid, gid and
mtime. A regular node also remains bounded by the TAR entry-payload cap. Across
composition, effective path plus link-target UTF-8 bytes are charged against an
8 MiB metadata budget; paths are limited to 32 components.

The rootfs evidence is a namespace/overlay composition bound transitively to the
verified layer DiffIDs. It does not claim extraction, host filesystem metadata,
xattrs, device nodes or runtime materialization.

## Whiteouts

An OCI whiteout is an empty regular entry named `.wh.<target>`. It removes only a
matching lower-layer node and its descendants. `.wh..wh..opq` hides all lower
children of its containing directory. Markers are never emitted as final nodes.

Each layer is evaluated in two phases: its markers affect the accumulated lower
state, then its ordinary entries are applied. Therefore a marker cannot remove a
file introduced by the same layer, independent of TAR entry order. Invalid,
non-empty or non-regular reserved markers fail closed.

Whiteout parent validation uses a bounded parent view consisting of the accumulated
lower state plus every directory declared by the current layer. Thus a same-layer
directory can supply the marker parent in either TAR order, while a same-layer file
or symlink parent fails closed. Removal itself still targets only accumulated lower
state; current-layer additions survive.

## Tree and links

Entry paths remain normalized POSIX paths. A later file replacing a directory
removes incompatible descendants; a later directory may replace a file. The
effective tree cannot contain a non-directory ancestor of another node.

Links are resolved only in the virtual container namespace. Absolute symlink
targets start at the image root and relative targets start at the link parent.
Traversal can never consult or escape to the host. Dangling symlinks remain valid
leaf metadata for compatibility until the real Laya topology is characterized,
but a later entry may not traverse an escaping, cyclic or dangling symlink
ancestor. A dangling symlink leaf is therefore valid evidence, not a materialized
filesystem claim.

Hardlinks are retained during overlay application and validated against the final
namespace after all ten layers. Forward targets and bounded hardlink chains are
valid only when they end at a final effective regular file; missing, cyclic or
non-regular final targets fail atomically.

## Budgets and evidence

Public positive constants bound 65,536 effective input entries, 4,096 whiteouts,
8 MiB of effective path/link metadata, 32 path components, 16 link hops and
131,072 mutations. TAR-width caps bound mode/uid/gid/mtime and the TAR payload cap
bounds each regular node. Subtree deletion charges every removed node. Exhaustion
fails before applying the next operation or layer and before any evidence sealer
is called.

A parent→direct-children index is built once and updated with every insertion and
subtree removal. Traversal is bounded by the remaining mutation budget; composition
does not repeatedly scan the whole namespace for each deletion.

The final nodes are canonically path-ordered and immutable. A private manifest
commitment is mutation-sensitive but absent from repr and the public summary.
The summary contains only schemas, runtime identity and conservative claims.

Evidence construction and every summary revalidation rederive root metadata and
all final nodes from the exact sealed TAR plan, compare them to the stored values,
and recompute the private manifest commitment. Forged nested state cannot acquire
authority by recomputing only its digest.

The real-layout gate composed 56,996 TAR entries into 56,114 final nodes. That
evidence sets only `oci_rootfs_verified=true` beyond inherited PR32 claims;
`rootfs_materialized=false` and all origin/license/base/executor/inference claims
remain false.

## Operational isolation

No adapter is needed: secure same-root capture already happened in PR32. The new
module is not imported by backend, scripts, runners, readiness or dataset code.
Historical scenario tests remain mandatory regression gates.

