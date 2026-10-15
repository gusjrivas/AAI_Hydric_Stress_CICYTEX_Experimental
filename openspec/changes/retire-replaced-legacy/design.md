## Context

`SQLiteSessionRepository` and `SQLiteCicytexFeedbackRepository` share
`cicytex_replay_sessions.sqlite3`.  The default is under `/workspace/data`, while
`compose.cicytex.yml` only persists `/workspace/cicytex-feedback` and still exports the obsolete
`CICYTEX_REPLAY_FEEDBACK_DIR`.  Removing the old mount would discard the only stable upgrade and
rollback location; keeping the stale variable would leave the active database ephemeral.  The
active named volume also contains `/workspace/cicytex-feedback/feedback.json`, but production only
imports that file when `CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON` names it explicitly.  With the new
empty default, that behavior could silently bootstrap an empty database beside preserved feedback.

## Decision

The deployment SHALL set
`CICYTEX_REPLAY_SESSION_DB=/workspace/cicytex-feedback/cicytex_replay_sessions.sqlite3`, remove
`CICYTEX_REPLAY_FEEDBACK_DIR`, and declare
`CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON=${CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON:-}`.  The empty default
keeps fresh volumes valid without inventing a legacy file.  An existing deployment MAY opt in
with the exact override only when its authoritative source database contains every matching
replay session required for full importer validation:
`CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON=/workspace/cicytex-feedback/feedback.json` for its migration
window.  A feedback-only volume MUST remain unimported and preserved for manual reconciliation.
Compose also SHALL set
`CICYTEX_REPLAY_LEGACY_FEEDBACK_DISCOVERY=/workspace/cicytex-feedback/feedback.json`.  Discovery is
existence-sensitive: an absent file resolves to no import, while a present file is passed to the
repository and therefore either validates against authoritative sessions or makes startup fail
closed.  When discovery policy is configured, a non-empty explicit override MUST equal that path;
arbitrary administrator-controlled legacy paths remain supported only outside deployment policy
(for tests and local tooling).
Both modes preserve the `cicytex-feedback` compose key and external name
`aai-cicytex-experiment-feedback`.  The database parent, migration-file parent and mount target
form one closed contract, verified by parsing Compose rather than matching independent strings.

## Live migration and rollback gate

Moving a live database is a P0 data operation, not a file-copy convenience.  Before changing the
deployment, an operator MUST:

1. quiesce all writers, or use SQLite's online backup API from one controlled connection;
2. checkpoint WAL state under the same discipline and never copy only the main file while writers
   remain active;
3. retain the source database, its WAL/SHM companions and the original `feedback.json` as a
   rollback set; the staging tool never deletes or replaces source sidecars;
4. record SHA-256 and byte size for the captured database;
5. run `PRAGMA integrity_check` on the destination;
6. record source-snapshot version, integrity and row counts, then require destination sessions to
   equal source sessions and destination feedback to equal source feedback plus validated legacy
   imports;
7. start the service against the destination and perform a read-only verification before allowing
   writes; and
8. keep the source untouched until the verification window closes, with a documented rollback
   command that restores the original database path.

Failure at any step leaves the source authoritative and aborts deployment.  Compatibility
importers and the v1-to-v2 migration remain until a separate, evidence-backed sunset decision.
An existing WAL is byte-stable evidence and must remain byte-identical.  A sidecar that appears
after preflight is a concurrent-write race and aborts without being removed.  SHM remains
source-owned and must never be deleted or replaced, but SQLite reader marks are ephemeral, so the
contract intentionally does not promise SHM byte identity during online backup.

## Test strategy

A parsed Compose contract validates the durable database, empty-default legacy interpolation,
exact discovery path, mount source/target and external volume identity together.  Runtime tests
cover absent discovery, detected feedback, conflicting explicit overrides and feedback-only
fail-closed behavior.  Mutation cases cover stale,
missing or fixed-value variables, migration paths outside the mount, and removed or renamed
mount/volume identities.
