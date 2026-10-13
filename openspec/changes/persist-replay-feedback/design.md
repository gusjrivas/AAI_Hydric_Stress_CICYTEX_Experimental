# Design: durable replay feedback

## Boundaries

`historical_replay.cicytex_feedback` owns records, validation, service errors and
the `CicytexFeedbackRepository` port.  The existing SQLite session adapter owns
schema v2 and the atomic session-plus-feedback transaction.  The CICYTEX router
does not import SQLite, JSON, filesystem paths or lock primitives.

Historical package feedback uses the separate
`historical_replay.adapters.sqlite_feedback.SQLiteReplayFeedbackStore`, behind
`HistoricalReplayFeedbackRepository`.  Its database and package namespace never
share tables or paths with CICYTEX sessions or operational human feedback.

## CICYTEX schema v2 and migration

Schema v2 preserves the closed v1 metadata and session table and adds a closed
`cicytex_replay_feedback` table keyed by the natural prediction identity
`(sensor_id, emission_date, horizon_days)`.  Opening a canonical v1 database
performs one transactional migration.  A configured legacy JSON document is
bounded, strict, closed-schema validated, digested and imported once in that
same transaction.  Invalid, partial, foreign, oversized or changed import
material fails closed without losing v1 sessions or exposing content.

Feedback registration begins an immediate transaction, reads the current
session, validates reveal state inside that transaction and inserts the natural
key before commit.  Reset and registration therefore have one serial order
across processes.  Callback failure or process-visible repository failure rolls
back both state observations and writes.  Duplicate natural identities map to
the existing HTTP 409 contract.

## Historical append-only store

The historical store uses a closed schema, monotonically ordered append key and
package namespace.  Legacy JSONL import is bounded, strict and all-or-nothing;
its digest is recorded once.  Concurrent adapters/processes append without lost
rows.  Reset only changes visibility through the simulated clock; it never
deletes feedback.  Corruption is reported through a private repository error.

## Failure and privacy model

Database, SQL, paths, legacy bytes and record contents do not appear in public
errors or logs.  Backend dependencies own administrator-controlled paths and
translate repository errors to the existing sanitized 503 envelope.  Imports
have explicit byte, record, line and string caps and reject duplicate JSON keys,
non-finite numbers, partial trailing lines and unknown fields.
