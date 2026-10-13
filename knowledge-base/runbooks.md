# Investigation Runbooks

These procedures are read-only. They are intended for a developer or an investigation model.

## Runbook 1: Start with the failed run

1. Record the Databricks job run ID, task key, start time, end time, retry count, and Git or notebook revision.
2. Record the first task that failed, not only the final job status.
3. Capture the complete exception and the first meaningful stack-trace location.
4. Map the task to the stage in [execution and dependencies](execution-and-dependencies.md).
5. Check whether the previous stage produced its expected file or table.
6. Continue with the stage-specific runbook below.

If the run ID, task key, logs, or code revision are unavailable, list them as missing evidence.

## Runbook 2: Investigate ingestion

Check:

1. Dataset name and CMS dataset ID.
2. CMS metadata response and `released` value.
3. CSV distribution URL and media type.
4. Download attempts and final exception.
5. Destination path, file size, header, and row count.
6. Volume permissions and available storage.

Interpretation:

- HTTP or metadata failure points to the CMS boundary or configuration.
- Successful metadata with failed file write points to network or volume handling.
- A successful request with an empty or malformed file requires raw-file inspection before Bronze analysis.

Relevant code: `get_csv_download_url`, `download_csv_to_volume`, `get_dataset_released_date`, and `src/ingest_task.py`.

## Runbook 3: Investigate Bronze

Check:

1. The raw path configured for the dataset.
2. Raw file row count and header.
3. Bronze table existence and schema.
4. Incoming source hash count.
5. Existing Bronze hash count.
6. Number of new rows written.
7. Any write or Delta permission error.

Interpretation:

- Zero raw rows is an upstream or file problem.
- Zero new Bronze rows can be a correct unchanged rerun; compare hashes before calling it a failure.
- Duplicate hashes indicate a deduplication or table-integrity problem.
- Missing `source_data`, `source_released_date`, or `source_hash` indicates a Bronze contract problem.

Relevant code: `read_raw_data`, `add_ingestion_metadata`, `add_source_hash`, and `write_bronze_table` in `src/bronze_job.py`.

## Runbook 4: Investigate the quality gate

For each Bronze table, collect:

```sql
SELECT COUNT(*) AS row_count,
       COUNT_IF(source_hash IS NULL) AS null_hash_count,
       COUNT(DISTINCT source_hash) AS distinct_hash_count
FROM <catalog>.bronze.<table_name>;
```

Then compare `row_count` with `distinct_hash_count` and inspect duplicate values if they differ.

Check the live table name and schema before running the query. The repository’s quality gate uses the configured catalog and Bronze schema. The freshness helper should be tested separately because its SQL expression needs validation.

## Runbook 5: Investigate Silver

For the affected dataset:

1. Compare current raw headers with `raw_field_names` in `config/datasets.py`.
2. Inspect a Bronze `source_data` sample for the required JSON keys.
3. Compare required columns with the extracted DataFrame columns.
4. Count rows before and after mandatory-key removal.
5. Count nulls in configured numeric and date columns after casting.
6. Count natural-key/quarter duplicates.
7. Compare the written Silver schema with the configured types.

Key questions:

- Did CMS rename a field?
- Did extraction use the exact CMS raw field name?
- Did a placeholder become null as intended?
- Did a cast convert unexpected values to null?
- Did mandatory-key removal discard records?
- Did deduplication remove more records than expected?

## Runbook 6: Investigate joined Silver

Check distinct key counts at each input:

```sql
SELECT COUNT(*) AS rows,
       COUNT(DISTINCT CONCAT_WS('|', facility_id, source_quarter)) AS facility_quarters
FROM <catalog>.silver.<table_name>;
```

For each measure dataset, compare its facility-quarter keys with `general_info`. Then inspect null counts for the aggregate columns in `hospital_summary`.

Interpretation:

- A facility missing from general information cannot become a base row in the left join.
- A facility-quarter mismatch produces null aggregate columns rather than necessarily removing the general-information row.
- A stale CMS dataset may legitimately have a different latest release date.

Relevant code: `create_joined_silver_table` in `src/silver_job.py`.

## Runbook 7: Investigate Gold

Check:

1. `silver.hospital_summary` exists and has rows.
2. The live schema contains every `METRIC_CONFIG.source_column`.
3. Numeric source columns have expected types and null counts.
4. Each affected facility has enough quarter history.
5. The Gold output table can be overwritten by the job identity.
6. Anomaly and trend counts match a manual sample calculation.

For a trend flag, manually check the five predicates in [business rules](business-rules.md). Do not confuse a missing trend flag with a pipeline failure; it may simply mean the data did not meet the rule.

## Runbook 8: Investigate alerting

1. Execute the checked-in alert SQL manually.
2. Compare its table reference with the live Gold table.
3. Compare every selected column with the live Gold schema.
4. Check the predicate and timestamp window.
5. Check alert schedule and execution history.
6. Check notification recipients and delivery status.

The checked-in JSON references names that differ from the visible Python code. Treat this as a configuration reconciliation task until live evidence proves an operational failure.

## Safe output

A runbook may recommend a query, source comparison, schema inspection, or human review. It must not recommend changing production data, deleting Bronze history, rerunning a job, or changing code without explicit human approval.
