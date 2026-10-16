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

## Tree and links

Entry paths remain normalized POSIX paths. A later file replacing a directory
removes incompatible descendants; a later directory may replace a file. The
effective tree cannot contain a non-directory ancestor of another node.

Links are resolved only in the virtual container namespace. Absolute symlink
targets start at the image root and relative targets start at the link parent.
Traversal can never consult or escape to the host. Dangling symlinks remain valid
leaf metadata for compatibility until the real Laya topology is characterized,
but a later entry may not traverse an escaping, cyclic or dangling symlink
ancestor. Hardlinks must resolve to an effective regular file.

## Budgets and evidence

Public positive constants bound effective nodes, whiteouts, metadata bytes, path
components, link hops and total mutations. Subtree deletion charges every removed
node. Exhaustion fails before applying the next operation or layer and before any
evidence sealer is called.

The final nodes are canonically path-ordered and immutable. A private manifest
commitment is mutation-sensitive but absent from repr and the public summary.
The summary contains only schemas, runtime identity and conservative claims.

## Operational isolation

No adapter is needed: secure same-root capture already happened in PR32. The new
module is not imported by backend, scripts, runners, readiness or dataset code.
Historical scenario tests remain mandatory regression gates.

