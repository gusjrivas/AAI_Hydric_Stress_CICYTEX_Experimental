# CICYTEX replay storage cutover

This runbook stages a new durable replay database without modifying the active named volume.  It
is an offline preparation step, not authorization to switch production or delete a source.

## Preconditions

1. Quiesce every replay-session and feedback writer, or capture the database with SQLite's online
   backup API while the source connection owns the snapshot.
2. Record SHA-256 and byte size for the SQLite input and, when present, `feedback.json`.
3. Keep the main database, WAL and SHM files together until backup completes.  Copying only the
   main file while writers are active is forbidden.
4. Select a new, absent, non-symlink staging directory outside the active volume path.  The tool
   refuses an existing directory and never stages in place.

## Source modes

- Existing SQLite source: pass `--source-database` and its expected SHA-256.  The tool snapshots
  it with SQLite backup, validates it through `SQLiteSessionRepository`, and uses
  `SQLiteCicytexFeedbackRepository` for any explicit legacy import.
- Truly empty deployment: pass `--empty-source`.  This creates an empty schema-v2 database.  It
  may not be combined with a non-empty legacy JSON file.

An active volume that contains only `feedback.json` does **not** have enough session lineage for
automatic import.  Preserve that JSON byte-for-byte and stop for manual reconciliation.  Never
fabricate sessions from feedback fields, and never mark such a deployment migrated.

The deployment sets
`CICYTEX_REPLAY_LEGACY_FEEDBACK_DISCOVERY=/workspace/cicytex-feedback/feedback.json` while keeping
`CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON` empty-default.  If the discovery file is absent, a fresh
volume starts normally.  If it exists, startup presents it to the repository so complete lineage
is imported or feedback-only/invalid state fails closed with the existing private storage error;
it must never silently create an empty database.  An explicit override under this deployment
policy must name exactly the discovery path.  Tests and local tools without a discovery policy may
still provide another administrator-controlled legacy path.

## Existing legacy feedback

Only use `--legacy-feedback-json` when a captured source database contains the matching replay
sessions.  Supply its expected SHA-256.  Any foreign, ambiguous, temporally invalid or unmatched
record aborts the whole stage.  The original JSON remains immutable and authoritative until the
cutover is independently accepted.

## Required evidence

The staging directory contains only `cicytex_replay_sessions.sqlite3` and
`cutover-evidence.json`.  Evidence records the input and staged digests, staged byte size, and the
source backup snapshot's user version, `PRAGMA integrity_check`, session count and feedback count.
It also records the destination's version, integrity and counts plus the number of legacy feedback
rows imported.  The destination session count must equal the source snapshot count; its feedback
count must equal source feedback plus the imported legacy count.  Empty-source evidence uses zero
source counts and null source version/integrity.  Evidence must not contain absolute paths,
feedback contents, observations or session identifiers.  Verification opens the staged database
read-only; a failed hash, backup, import, comparison, verification or atomic publish leaves no
output.

The tool never deletes or replaces a source `-wal` or `-shm` sidecar.  A WAL that existed before
capture must remain byte-identical.  A WAL or SHM that appears during capture is a concurrent-write
signal: staging aborts and leaves it in place.  SQLite's online-backup reader can update ephemeral
reader marks inside an existing SHM, so SHM byte identity is not evidence; its source ownership and
continued presence are.  This asymmetry does not weaken the WAL byte check.

Before deployment, independently recompute the staged digest, repeat `PRAGMA integrity_check`,
compare both row counts, and inspect the evidence schema.  Preserve the source database, WAL/SHM,
legacy JSON and their recorded hashes throughout the rollback window.  Switching Compose and
removing any source are separate approved operations.
