## ADDED Requirements

### Requirement: Exact preregistration authority binds a separate execution protocol

The system SHALL prepare a pure successor only from an exact issued and deeply
validated preregistration instance. It SHALL reject clones, stale records and
mutated bindings without changing legacy v1 public schema or scientific claims.

#### Scenario: Forged structural metadata is not scientific authority

- **GIVEN** a copied, rebound or directly constructed preregistration object
- **WHEN** successor protocol preparation is requested
- **THEN** it fails privately before any inference or private input consumption

### Requirement: Missing scientific authority blocks input consumption

The system SHALL require corpus custody, a frozen calibration method and the
separate corpus runtime profile before public execution reads comments or invokes
an executor. Missing authority SHALL remain explicitly BLOCKED.

#### Scenario: Missing method cannot open outer-test

- **GIVEN** the calibration cohort exists but no frozen method/release authority
- **WHEN** a scientific execution is requested
- **THEN** no comment or holdout reaches inference and calibration remains unfitted

### Requirement: Mechanical fixtures never become scientific results

The system SHALL implement and verify the runner/adapter using bounded mechanical
fixtures without treating them or PR41 smoke as scientific execution or readiness.

#### Scenario: A mechanical run is not scientific completion

- **GIVEN** a fixed synthetic fixture and a successful mechanical verification
- **WHEN** its result is summarized
- **THEN** scientific evaluation, calibration, attestation, sufficiency, shadow and
  production flags remain false and no private text/IDs/output rows are published
