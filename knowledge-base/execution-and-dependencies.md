# Execution and Dependencies

## Declared task order

The project README describes this Databricks job sequence:

```text
extract_source_data
    -> load_bronze_layer
    -> validate_bronze_quality
    -> silver_layer_transformation
    -> generate_gold_layer_risk_report
```

The checked-in Python wrappers map to the stages as follows:

| Task responsibility | Source entry point | Main dependency | Expected output |
|---|---|---|---|
| Extract source data | `src/ingest_task.py` | CMS metadata and CSV endpoints, Databricks volume | Five raw CSV files |
| Load Bronze | `src/bronze_job.py` | Raw CSV files, Spark, Delta tables | Five Bronze tables |
| Validate Bronze | `src/quality_gate.py` | Five Bronze tables | Pass or pipeline-stopping failure |
| Transform Silver | `src/silver_task.py` and `src/silver_job.py` | Bronze tables and dataset configuration | Five Silver tables plus `silver.hospital_summary` |
| Generate Gold | `src/gold_task.py` and `src/gold_job.py` | `silver.hospital_summary`, Spark window functions | `gold.hospital_risk_report` |
| Notify | Databricks SQL alert JSON | Gold table and saved query | Email notification when the alert condition is met |

The exact Databricks job configuration is not stored in this repository. The task names and dependency order above are therefore documented from the README and source entry points and should be verified against the live job.

## External dependencies

### CMS Provider Data API

The downloader calls the CMS metadata endpoint configured in `config/settings.py`. It uses the metadata response to find a CSV distribution and to read the dataset `released` date.

Failure examples:

- Metadata endpoint unavailable
- HTTP error
- Invalid JSON response
- No CSV distribution
- Missing `released` field
- Download timeout
- Partial or invalid downloaded file

### Databricks volume

The ingestion task writes files under the configured volume path in `config/datasets.py`. Bronze reads those paths. Permission, path, mount, and file-integrity problems can therefore prevent Bronze from starting.

### Spark and Delta

Bronze, Silver, and Gold use Spark DataFrames and Delta tables. The pipeline depends on the configured catalog, schemas, table permissions, Spark functions, window functions, and Delta write support.

### Databricks SQL alert

The alert depends on a valid saved query, a correct Gold table reference, the correct timestamp column, schedule permissions, and notification configuration. The checked-in alert JSON currently requires reconciliation with the Python table names before production diagnosis relies on it.

## Write behavior

| Layer | Write behavior | Debugging meaning |
|---|---|---|
| Raw files | Download/overwrite configured CSV paths | A raw file may represent the latest download, not an immutable release history |
| Bronze | Create once, then append unseen content hashes | A rerun with identical row content should add no rows |
| Silver dataset tables | Overwrite | A failed or partial write may leave the previous table or no new table depending on the job state |
| `silver.hospital_summary` | Overwrite | It is rebuilt from the Silver dataset tables |
| Gold report | Overwrite | It is fully recomputed from the joined Silver table |

## Retry behavior

The CMS CSV download retries three times, waiting ten seconds between attempts. The source code logs each failed attempt and raises a final `RuntimeError` after the last attempt.

The repository does not define a general retry policy for Spark stages. Databricks task retry behavior must be read from the live job run configuration.

## Failure localization order

When investigating a run, check the earliest failed stage first:

1. CMS metadata/download and raw file availability
2. Bronze table creation or append
3. Bronze quality gate
4. Per-dataset Silver processing
5. Joined Silver table creation
6. Gold calculations or write
7. Alert query, schedule, or notification

A downstream failure is often a consequence of an earlier missing or invalid output. Do not begin with Gold logic until the joined Silver output is confirmed.

## Known configuration conflicts to verify

- Python code uses catalog `Hospital_Risk_Analysis`; the checked-in alert JSON references `hospitalchecks`.
- Gold Python code writes a table with the configured catalog and `gold.hospital_risk_report`; the alert JSON uses a different fully qualified table reference.
- Gold Python code rounds and writes `ingestion_timestamp` inherited from Silver; the alert JSON filters on `ingestion_timestamp_ist`.
- `CMS_ALERT_THRESHOLD` exists in `src/gold_job.py` but is not used in the visible Gold calculation path.
- The freshness helper in `src/quality_gate.py` should be validated because its SQL expression appears to reference a quoted column name.

These are evidence-backed review items. They should be confirmed against live schemas, query history, and the deployed alert before being labeled as runtime incidents.
