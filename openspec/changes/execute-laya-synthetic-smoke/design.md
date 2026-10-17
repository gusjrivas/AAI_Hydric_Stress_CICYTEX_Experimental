# Fixed synthetic execution boundary

## Pure authority

`runtime_execution.py` binds the exact live issued PR40 evidence, original plan,
runtime identity, derived image and installation commitment. Reject clones,
replacement, rebinding, revocation and deep mutation. Preparation performs no I/O
and leaves both execution claims false. Issuance requires an adapter-controlled
private receipt after successful child cleanup, not arbitrary JSON or a dataclass.
Public summaries omit input/output text, probabilities, image IDs and commitments.

Plans, one-shot receipts and evidence have exact-instance weak issuance records.
The core revalidates the shared pure observation schema and exact canonical bytes
before issuing a receipt. It retains only a private SHA-256, never observation
bytes. The evidence and its issuance record retain that commitment after receipt
consumption; mutation or stale/foreign records cannot restore authority. Only
schema, the fixed execution profile and the 35 explicit claims reach a summary.

## Closed smoke profile

Use `docker-local-offline-cpu-synthetic-v1`, one short explicitly synthetic ASCII
state and one `choice` question with ordered categories `data_quality`,
`model_behavior`, `agronomic_context`, `usability`, `other`. The model is forced to
`multilingual`. No caller-controlled executable, route, environment or task file.
Bound every field/token/response; reject booleans as numbers, nonfinite values,
unknown/missing/duplicate keys, categories/order drift and invalid probability
mass. Preserve `confidence` and `answer_confidence` as distinct observations.
Run twice and require identical canonical decision bytes; timing is not part of
that commitment. This is determinism of one smoke fixture, not scientific quality.

## Lifecycle

Acquire a descriptor-free per-runtime image lease serialized against disposal.
Keep the PR40 restrictions: local trusted daemon, CPU, numeric nonroot user,
read-only filesystem, network none, no capabilities/devices/host mounts or ports,
builtin seccomp, no-new-privileges, bounded logs/tmpfs/resources and total deadlines.
Create only the owned fixed smoke child, inspect before start, validate exit/OOM,
recapture bounded output, remove the child, then release the lease. Any failure
keeps execution claims false and preserves owned cleanup retry semantics.

Each execution uses a fresh local engine and nonce, not the engine that owns the
runtime image. The execution engine never imports, adopts or owns that image.
Profiles are bound through intent, ownership, inspection, start and wait; loader
and synthetic paths cannot cross. Normal failure cleanup is attempted inside the
image lease. Pending cleanup can only be retried through the exact private error
handle. Receipt and evidence issuance occur after successful cleanup, still in
the lease. A lease-exit failure revokes partial evidence; if ordinary revocation
fails, exact-instance private discard removes issuance authority without I/O.

The existing human-feedback HTTP adapter and LOSO evidence contracts are separate
and unchanged. No scientific claim is inferred from smoke output.
