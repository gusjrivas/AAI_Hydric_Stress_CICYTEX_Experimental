# Pure calculations, private pairing, separate government

## Small additive boundary

Add one `evaluation_statistics.py` module with pure arithmetic helpers and a
private protocol/receipt bridge. Reuse category constants, existing confidence
fallback semantics and the deterministic rule baseline for mechanical fixtures.
Do not instantiate legacy `OfflinePrediction` or call `evaluate_readiness`:
their HTTP provenance, unique argmax, probability tolerance and measurement inputs
are not the offline-v2 contract. Do not change those working v1 APIs.

The public preflight inspects neither its protocol argument nor private rows and
reports missing real corpus/custody, baseline producer, admitted analysis profile,
calibration evidence and latency inputs. Private fixture authorization defaults to
failure. No public boolean, result constructor or fixture grant authorizes READY.
Keep final evidence small and immutable; at most one issuance/binding boundary,
not a registry or hierarchy for every arithmetic helper.

## Pairing and privacy

Revalidate the exact issued protocol and all sealed batches. Calibration receipts
must exist and remain bound but never enter the outer-test estimands. Join each
test ordinal to the exact fold's ordered test records; every outer record appears
once across three sites. Runtime/model/port identity, phase, count and original
response commitments stay checked. Gold/site/group remain host-side. No inference,
model load, baseline network call, fitting or new holdout access occurs.

Baseline output must cover the same rows. Fixture baseline production is evaluated
once per outer-test row; real baseline protocol identity/digest/code admission is
still missing and cannot be inferred from the fixture. Summaries and errors never
contain comments, example/group IDs, labels or per-example predictions.

## Metrics and availability

Preserve offline-v2 rounded probabilities and selected categories, including
selected categories sharing a rounded maximum. Never renormalize or silently
replace a selected category. Compute raw accuracy, five-label macro-F1 with
zero_division=0, multiclass Brier and ten-bin ECE descriptively.

For separate legacy-policy diagnostics only, use the existing explicit fallback
`answer_confidence=None -> probabilities[selected_category]`, threshold 0.85,
abstention cost 1, incorrect answer cost 5 and correct answer cost 0. Report the
confidence source and uncalibrated status; do not invent an answer-confidence
measurement or calibration fit. Coverage, selective accuracy, policy accuracy,
policy macro-F1 and cost can be reported as those labeled mechanical diagnostics.
They do not choose the real study's primary pre/post-policy estimand.

Per-example p50/p95 latency is UNAVAILABLE_INPUT_NOT_CAPTURED; do not substitute
batch timing or 0ms. Calibrated scores and calibration fitting remain UNAVAILABLE.
Actual scientific decisions remain BLOCKED even when descriptive numbers exist.

## Paired resampling mechanics

Primary mechanical fixture estimand: equal-site mean of raw categorical macro-F1
Laya-minus-baseline deltas; site estimands use the same raw categories. This is
explicitly not admission of the study's calibrated/policy output stage.

Preaggregate paired confusion counts by group within site, retaining an abstention
column where needed. Sample exactly the original group count with replacement
within each site; identical multiplicities apply to both models. Keep fixed five
gold labels even when a bootstrap sample omits a class. Use the versioned fixture
profile in the proposal, B=10000, seed 20261017, 95% nearest-rank descriptive bounds.
Bound work/memory before resampling; do not create duplicated private rows or
refit/reclassify baseline inside a replicate. Keep only aggregate replicate values.

For each hypothesis use `(1 + count(delta_bootstrap <= margin)) / (B + 1)`;
margin global 0.05, each site -0.02. Holm orders by p then preregistered family
index, compares against alpha/remaining with alpha=0.05, stops at first failure
and requires all four rejections. Intervals never substitute for this rule.
Fixture numerical rejection is labeled mechanical, never scientific PASS.

## Evidence is not readiness

Final aggregates bind privately to protocol, sealed outputs, fixture baseline and
technical profile. Detect parent/receipt mutation before reuse. No raw rows are
duplicated or exposed. Scientific execution, fitted calibration, sufficiency,
shadow eligibility and production flags stay false. PR44 owns the decision and
must fail closed on any unavailable or externally unadmitted prerequisite.
