# Quality and Observability

## Existing checks

### Ingestion

The downloader logs metadata resolution, download attempts, destination path, completion, and retry errors. The ingestion task collects dataset failures and raises a final error if any dataset failed.

Source: [src/ingest_task.py](../src/ingest_task.py), [pipeline/ingestion/cms_api_downloader.py](../pipeline/ingestion/cms_api_downloader.py)

### Bronze

Bronze logs raw row count and column count, table creation, new-row count, duplicate-only reruns, and dataset start/end messages.

Source: [src/bronze_job.py](../src/bronze_job.py)

### Bronze quality gate

The quality gate checks that each Bronze table is non-empty, has no null hashes, and has no duplicate hashes.

Source: [src/quality_gate.py](../src/quality_gate.py), symbol `check_table`

### Silver

Silver logs per-dataset start and completion, Bronze count, missing required columns, rows before and after mandatory-key removal, rows before and after duplicate removal, and final Silver count. It raises when required fields are missing or a dataset fails.

Source: [src/silver_job.py](../src/silver_job.py), symbols `select_required_columns`, `remove_null_records`, `remove_duplicates`, and `process_silver_dataset`

### Joined Silver

The joined Silver step logs the final joined row count after building `silver.hospital_summary`.

Source: [src/silver_job.py](../src/silver_job.py), symbol `create_joined_silver_table`

### Gold

Gold logs input count, transformation stages, output write, anomaly count, and early-warning count. Its task wrapper logs the exception and re-raises it.

Source: [src/gold_job.py](../src/gold_job.py), [src/gold_task.py](../src/gold_task.py)

## Evidence to collect for a failed run

| Evidence | Why it matters |
|---|---|
| Job run ID and task key | Identifies the incident and failing boundary |
| Task status and retry count | Distinguishes code failure from transient retry behavior |
| Start/end timestamps | Builds a timeline and identifies slow stages |
| Runtime and cluster details | Explains environment-specific behavior |
| Git revision or notebook version | Connects runtime behavior to code |
| Full exception and first meaningful stack trace | Identifies the failure mechanism |
| Dataset name and CMS ID | Identifies the affected source contract |
| CMS release date and metadata response | Distinguishes upstream freshness from processing failure |
| Raw file path, size, header, and row count | Detects missing or partial input |
| Bronze row count and new-row count | Detects ingestion and deduplication effects |
| Quality-gate results | Confirms whether Bronze was valid |
| Silver before/after counts | Detects cleaning, casting, and key loss |
| Table schemas | Detects schema drift and missing columns |
| Joined Silver count | Detects join or aggregation loss |
| Gold input/output and flag counts | Detects metric and write failures |
| Alert query and result | Separates Gold correctness from notification failure |

## Current observability gaps

The project does not currently persist a single incident record containing all of the evidence above. It also does not visibly add a shared run ID to every log line or write a stage metrics table.

Other gaps:

- Freshness is warned about but not clearly enforced as a stop condition.
- There is no formal schema-contract history for CMS releases.
- There is no standard record of how many rows were lost at each transformation boundary.
- There is no stable alert-delivery result in the repository.
- There is no documented SLA for source freshness or alert delivery.
- The exact Databricks task retry configuration is external to this repository.

These gaps should be reported as missing evidence during RCA.

## Recommended diagnostic fields

If logging is extended, each stage event should include:

```text
run_id
job_id
task_key
stage
dataset_name
dataset_id
source_released_date
table_name
started_at
finished_at
status
input_row_count
output_row_count
rows_removed
error_type
error_message
git_revision
```

Do not include secrets, tokens, credentials, or raw sensitive payloads in structured logs.
