# Separate mechanism from scientific authority

## Reuse, do not reinterpret

Keep evaluation corpus/split/preregistration semantics and v1 public summaries.
The split already freezes group-safe calibration cohorts, not a calibration
algorithm. Add exact-instance weak preregistration issuance/deep validation for
the successor, then a pure `evaluation_run_protocol.py` with no I/O or synthetic
executor dependency. Runtime and actual offline execution are separate adapters.

PR41 smoke is an operational prerequisite only. Never convert its two synthetic
execution claims into LOSO execution, calibration, sufficiency or readiness.
Use a distinct offline provider/profile instead of the legacy `laya-http`.

## Input custody

The inference port receives an immutable private opaque token and comment only.
Gold, annotator/adjudication state, group/site/example identifiers and full corpus
objects stay host-side. Fixed child code consumes bounded canonical stdin and
returns a closed, bounded ordinal/category/probability response. The host resolves
ordinals privately and verifies exact order/coverage, runtime/model and protocol
commitments. A public preflight with missing authorities consumes no comment and
does not invoke the port.

The pinned upstream reports token usage and truncation. Corpus execution must
not silently score a prefix as the complete comment: the closed response must
carry bounded usage/truncation metadata and reject dropped/truncated input unless
an externally frozen protocol explicitly authorizes that exact preprocessing.
A byte-size cap alone does not prove that text fits the tokenizer/model budget.

## Lifecycle and phase order

Per fold: freeze exact calibration cohort -> predict -> seal mechanical receipt
-> require authorized calibration release -> predict exact outer-test cohort ->
seal outputs. Missing release cannot open test. Leases, fresh child ownership,
timeouts/resource limits, cleanup-before-release and fail-closed partial evidence
follow the reviewed runtime boundary without weakening loader/synthetic profiles.
Resume/concurrency must not replay or duplicate an accepted outer prediction.

## Scientific gates

The current repository lacks real private corpus/custody and a frozen calibration
method. Default statuses are `BLOCKED_CORPUS_NOT_PROVIDED`,
`BLOCKED_CALIBRATION_METHOD_NOT_FROZEN` or
`BLOCKED_RUNTIME_PROFILE_NOT_AUTHORIZED`. No caller boolean can authorize READY.
Fixture grants live only in test seams, never a production bypass or conversion
to scientific authority. Mechanical evidence keeps evaluation/calibration/
gold-blind scientific attestation/sufficiency/shadow/production false.

No fitting, tuning, scoring, bootstrap, Holm or interpretation in this change;
those must consume the existing preregistration without methodological invention.
