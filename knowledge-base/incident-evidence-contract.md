# Incident Evidence Contract

## Purpose

A failed-run investigation needs one consistent evidence package. This contract defines the information the model should receive or retrieve. It does not require every field to exist today; unavailable fields must be marked explicitly.

## Incident envelope

```yaml
incident_id: required
job_id: required_if_available
run_id: required_if_available
reported_at: required
trigger: required
status: required
code_revision: recommended
runtime: recommended
```

## Task record

For every task in the run, collect:

```yaml
task_key: required
task_name: recommended
stage: required
status: required
attempt: recommended
started_at: recommended
finished_at: recommended
duration_seconds: recommended
error_type: required_if_failed
error_message: required_if_failed
log_reference: required_if_available
```

## Dataset record

For every affected dataset, collect:

```yaml
dataset_name: required
dataset_id: required
raw_path: required_if_available
cms_release_date: recommended
metadata_reference: recommended
download_status: required_if_available
download_attempts: recommended
file_size_bytes: recommended
header: recommended
raw_row_count: recommended
```

## Table evidence

For every relevant table, collect:

```yaml
table_name: required
layer: required
exists: required
schema_reference: recommended
schema_snapshot: recommended
row_count: recommended
business_key_count: recommended
null_counts: recommended
duplicate_counts: recommended
freshness: recommended
query_reference: recommended
observed_at: required_if_available
```

## Stage metrics

The preferred stage metrics are:

```yaml
stage: required
input_count: recommended
output_count: recommended
rows_removed: recommended
rows_added: recommended
null_count_changes: recommended
duplicate_count_changes: recommended
status: required
```

## Evidence status values

Use one of these values for every field:

- `observed`: directly returned by a tool or runtime record
- `source_defined`: defined in versioned code/configuration
- `derived`: calculated from observed evidence
- `unavailable`: the tool or environment could not provide it
- `not_applicable`: not relevant to this incident
- `conflicting`: multiple sources disagree

## Minimum complete packet

A packet is minimally useful when it contains:

1. A run identifier or a clear statement that none is available.
2. The first failed task and its stage.
3. The exception or a clear statement that logs are unavailable.
4. The expected input and output for that stage.
5. At least one check of the preceding stage.
6. Code/configuration references for the affected behavior.
7. Missing-evidence fields.

## Model rule

The model must never treat an unavailable field as evidence that the field was empty, valid, or failed. It must say that the evidence was unavailable.
