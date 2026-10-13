# System Overview

## One-sentence description

This project downloads five public CMS hospital-quality datasets, preserves them in Bronze, cleans and joins them in Silver, calculates hospital risk and trend signals in Gold, and sends a Databricks SQL alert for new declining-trend flags.

## End-to-end flow

```text
CMS Provider Data API
    |
    v
Ingestion task
    |
    v
Raw CSV files in Databricks volume
    |
    v
Bronze tables: original row as JSON plus ingestion metadata
    |
    v
Bronze quality gate
    |
    v
Silver dataset tables: extracted, cleaned, typed, deduplicated rows
    |
    v
silver.hospital_summary: one hospital-quarter row with aggregates
    |
    v
Gold hospital_risk_report: scores, tiers, anomalies, and trend flags
    |
    v
Databricks SQL alert and email notification
```

## Stage responsibilities

### 1. Ingestion

The ingestion task loops through the five configured datasets. For each dataset it asks the CMS metadata endpoint for a CSV distribution, downloads the CSV to its configured raw path, and retries failures up to three times with a ten-second backoff.

Primary evidence:

- `src/ingest_task.py`
- `pipeline/ingestion/cms_api_downloader.py`
- `config/datasets.py`
- `config/settings.py`

### 2. Bronze

Bronze reads each raw CSV without inferring data types. It converts the full row to JSON, keeps null keys in the JSON, adds the CMS release date and ingestion timestamp, calculates a SHA-256 content hash, and appends only hashes that are not already present.

Bronze is intended to be an append-only audit trail. It does not apply business transformations.

Primary evidence:

- `src/bronze_job.py`
- `config/datasets.py`

### 3. Quality gate

The quality gate checks every configured Bronze table for:

- At least one row
- No null `source_hash`
- No duplicate `source_hash`

The job should stop if one of these checks fails. A freshness helper also compares release dates, but the current implementation logs a warning instead of failing the pipeline.

Primary evidence:

- `src/quality_gate.py`

### 4. Silver

Silver extracts configured raw fields from the Bronze JSON payload, derives `source_quarter`, keeps the latest record for each natural key and quarter, selects required columns, cleans strings, converts known placeholders to null, casts configured types, drops rows missing mandatory keys, removes duplicates, and writes one Silver table per dataset.

The joined Silver step aggregates measure-level data by `facility_id` and `source_quarter`, then left-joins the five dataset outputs into `silver.hospital_summary`.

Primary evidence:

- `src/silver_job.py`
- `src/silver_task.py`
- `config/datasets.py`

### 5. Gold

Gold reads `silver.hospital_summary` and calculates quarter-relative z-scores, a weighted composite risk score, risk tiers, quarter-over-quarter anomaly flags, an internally derived star rating, and an early-warning declining-trend flag. It overwrites the Gold table on each run.

Primary evidence:

- `src/gold_job.py`
- `src/gold_task.py`

### 6. Alerting

The checked-in alert definition is intended to notify a distribution list when records are flagged for declining trend. The alert runs on a schedule and queries a Gold table.

The alert definition must be checked against the live Databricks workspace before it is treated as operationally correct. The checked-in JSON uses a different catalog/table reference and timestamp column name from the current Python code. This is a verified documentation/configuration conflict, not an assumed runtime failure.

Primary evidence:

- `Hospital Trend Decline Alert.dbalert.json`
- `src/gold_job.py`
- `README.md`

## Current investigation boundary

The first investigation workflow starts with a failed Databricks pipeline run. The model should identify the failed task and stage, collect evidence, and recommend the next read-only check. It should not assume the presence of a UI, product API, Kafka, Kubernetes, or application service layer because those components are not implemented in this repository.
