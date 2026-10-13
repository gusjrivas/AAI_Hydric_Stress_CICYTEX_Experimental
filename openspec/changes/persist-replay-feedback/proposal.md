# Change: Persist replay feedback atomically

## Why

Replay sessions are durable, but CICYTEX feedback still lives in a process-local
JSON document and historical-package feedback in append-only JSONL files.  A
reset can therefore race a feedback write, malformed legacy files can partially
affect startup, and concurrent processes do not share one transactional source
of truth.

## What Changes

- Upgrade the CICYTEX session database from schema v1 to v2 without losing
  sessions and persist feedback in the same SQLite transaction boundary.
- Import the legacy CICYTEX JSON document exactly once with a content digest,
  closed validation, bounded input and atomic failure.
- Introduce a domain-owned `CicytexFeedbackRepository` and feedback service;
  routers retain only HTTP translation and dependency injection.
- Replace historical replay JSONL persistence with an isolated SQLite
  append-only repository, including one-time bounded legacy import.
- Preserve all existing HTTP status codes and payloads while mapping private
  repository failures to a sanitized 503 response.

## Out of Scope

- Editing scientific replay packages, recalibration, retraining or promoting
  demonstration feedback to scientific ground truth.
- Deleting or rewriting accepted feedback rows.
- Client-selected database or import paths.
