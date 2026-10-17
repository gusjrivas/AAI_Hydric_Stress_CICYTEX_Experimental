## ADDED Requirements

### Requirement: Readiness separates diagnostics from scientific authority

The system SHALL evaluate available exact statistical aggregates and frozen gates
while retaining separate mechanical and scientific criterion states.

#### Scenario: Fixture rejection does not admit a scientific result

- **GIVEN** exact issued fixture evidence with passing or failing numeric gates
- **WHEN** readiness is evaluated
- **THEN** scientific criteria remain unadmitted and the overall result is BLOCKED

### Requirement: Readiness uses complete closed decision precedence

The system SHALL require complete verified prerequisites and passing authoritative
criteria for PASS, preserve a conclusive authoritative FAIL, and report missing
inputs as BLOCKED without invented values.

#### Scenario: Latency was not captured

- **GIVEN** no per-example latency measurement
- **WHEN** the latency criterion is evaluated
- **THEN** it remains NOT_EVALUATED rather than using zero or batch/bootstrap time

### Requirement: Terminal reports retain exact private authority

The system SHALL bind reports to exact unchanged issued statistics and expose only
closed privacy-safe summaries. Invalid/tampered evidence SHALL NOT issue a decision.

#### Scenario: Nested statistics mutate after report issuance

- **GIVEN** a previously issued report whose private parent is subsequently altered
- **WHEN** its canonical summary is requested
- **THEN** it fails privately without exposing comments, labels or private references

### Requirement: Technical completion never enables production

The system SHALL keep production permission false in every state, and SHALL NOT
infer scientific completion or shadow eligibility from synthetic fixtures.

#### Scenario: Mechanical plan is complete but real admissions are absent

- **GIVEN** all technical gates pass but scientific prerequisites are unavailable
- **WHEN** the final architecture status is reported
- **THEN** technical completion and scientific BLOCKED are reported separately
