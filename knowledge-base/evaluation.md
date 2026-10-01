# Evaluation Scenarios

## Purpose

These scenarios test whether an investigation model can localize a failure, use the right evidence, avoid unsupported claims, and recommend a safe next check.

The first fixtures may be manual JSON or Markdown packets. They do not need live Databricks access.

## Scenario template

```yaml
scenario_id: unique-name
failure_stage: expected stage
symptom: what the user sees
available_evidence:
  - run metadata
  - task log
  - table profile
  - source/config reference
expected_behavior:
  failing_stage: required answer
  supported_root_cause: required or not established
  hypotheses: expected ranked possibilities
  next_check: required read-only check
must_cite:
  - required source or runtime reference
forbidden_claims:
  - unsupported conclusion
```

## Initial synthetic scenarios

### KB-001: CMS metadata endpoint failure

- Failure stage: ingestion
- Symptom: metadata request returns HTTP 503 for one dataset
- Required conclusion: ingestion is the first failed stage
- Required next check: retry metadata access and compare the response with a known-good dataset
- Must not conclude: Silver or Gold logic is broken

### KB-002: Missing CSV distribution

- Failure stage: ingestion
- Symptom: metadata response has no CSV distribution
- Required conclusion: source contract or dataset metadata problem
- Required next check: inspect the metadata payload and compare the configured dataset ID
- Must not conclude: network failure without HTTP evidence

### KB-003: Empty raw file

- Failure stage: raw-file handoff or ingestion
- Symptom: download returns successfully but file size is zero
- Required conclusion: Bronze has not yet been proven to be at fault
- Required next check: inspect download response, destination write, header, and row count

### KB-004: Bronze duplicate hash failure

- Failure stage: Bronze or quality gate
- Symptom: quality gate finds repeated `source_hash` values
- Required conclusion: Bronze integrity check failed
- Required next check: compare incoming hashes, existing hashes, and the append join
- Must not conclude: duplicate business records without inspecting the source content

### KB-005: Silver field drift

- Failure stage: Silver
- Symptom: required column is missing during selection
- Required conclusion: Silver cannot satisfy its configured source contract
- Required next check: compare CMS header, Bronze JSON keys, `raw_field_names`, and `required_columns`

### KB-006: Silver cast loss

- Failure stage: Silver data cleaning
- Symptom: a numeric column has an unexpected rise in nulls after casting
- Required conclusion: data loss at or before the cast boundary is plausible
- Required next check: compare raw values with the configured target type and placeholder rules

### KB-007: Joined Silver key mismatch

- Failure stage: joined Silver
- Symptom: general-information rows exist but measure aggregates are null
- Required conclusion: this may be a release timing or facility-quarter key mismatch
- Required next check: compare distinct facility-quarter keys and dataset release dates

### KB-008: Gold source-column mismatch

- Failure stage: Gold
- Symptom: Gold fails because a configured metric source column is missing
- Required conclusion: Gold input schema and `METRIC_CONFIG` disagree
- Required next check: inspect live `silver.hospital_summary` schema and the current Gold source

### KB-009: Alert table mismatch

- Failure stage: alerting
- Symptom: Gold contains qualifying rows but the alert query fails or returns no rows
- Required conclusion: alert connectivity or query contract is suspect, not necessarily Gold logic
- Required next check: execute the exact alert SQL against the live table and compare schema/column names

## Scoring rubric

Score each investigation from 0 to 2 in each category:

| Category | 0 | 1 | 2 |
|---|---|---|---|
| Stage localization | Wrong or missing | Correct with weak reasoning | Correct and evidence-backed |
| Evidence use | Invented or irrelevant | Some relevant evidence | Uses all key evidence correctly |
| Citations | Missing | Partial | Every material claim is traceable |
| Confidence | Overconfident | Partly calibrated | Clearly separates fact, hypothesis, and unknown |
| Next check | Unsafe or irrelevant | Plausible but broad | Read-only and discriminates between causes |
| Scope discipline | Invents future components | Minor scope drift | Uses only current project evidence |
| Response completeness | Missing timeline/status | Partial report | Required RCA format is complete |

A first prototype should achieve at least 12 out of 14 on every core scenario and must score 2 for scope discipline and safety.
