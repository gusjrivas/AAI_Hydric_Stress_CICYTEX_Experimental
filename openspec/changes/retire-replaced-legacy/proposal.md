# Change: Retire replaced legacy paths safely

## Why

The CICYTEX replay runtime now persists sessions and feedback in one SQLite database, but the
deployment still mounts the historical feedback volume under an environment variable no current
code reads.  The active database therefore falls back outside that mount and can be lost when the
container is recreated.  Legacy retirement must first preserve durable data and a verifiable
rollback path.

## What changes

- Bind the active CICYTEX replay SQLite database to the existing named feedback volume.
- Bind the existing `feedback.json` to the explicit compatibility importer in that same volume.
- Remove the obsolete CICYTEX feedback-directory environment variable without renaming or
  abandoning the existing volume.
- Require a safe live-data migration and rollback record before deleting any compatibility
  importer, schema migration, adapter or persisted artifact.
- Retire only code and configuration proven to have no productive, dynamic or recovery consumer.

## Out of scope

- Removing SQLite schema-v1 migration, `feedback.json`, or the JSON/JSONL compatibility importers.
- Renaming the existing Docker volume or deleting persisted feedback/session data.
- Removing active frontend clients, backend schemas, repositories or test port adapters.
