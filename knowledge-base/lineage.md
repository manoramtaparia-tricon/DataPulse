# Data Lineage

## Lineage summary

```text
CMS dataset metadata and CSV
    -> raw CSV in Databricks volume
    -> Bronze source_data JSON
    -> extracted Silver columns
    -> cleaned and typed Silver rows
    -> facility-quarter aggregates
    -> silver.hospital_summary
    -> Gold z-scores and risk calculations
    -> gold.hospital_risk_report
    -> alert query
```

## Source to Bronze

1. `config/datasets.py` identifies the CMS dataset and raw path.
2. `pipeline/ingestion/cms_api_downloader.py` reads CMS metadata, resolves the CSV URL, and downloads the file.
3. `src/bronze_job.py` reads the CSV as strings.
4. The source row is serialized into `source_data` JSON.
5. `source_released_date`, `ingestion_timestamp`, and `source_hash` are added.
6. Rows whose content hash already exists in the Bronze table are skipped.

Bronze preserves source content but does not preserve a separate immutable copy of every downloaded file path. The Bronze table is the intended audit trail.

## Bronze to Silver

For each dataset, `src/silver_job.py`:

1. Reads the Bronze table.
2. Extracts configured raw field names from `source_data`.
3. Normalizes field names to lower-case underscore names.
4. Derives `source_quarter` from `source_released_date`.
5. Keeps the newest ingestion for each natural key and quarter.
6. Selects configured required columns.
7. Trims strings and replaces configured placeholder values with null.
8. Removes control characters.
9. Applies configured numeric and date casts using tolerant conversion functions.
10. Removes rows missing mandatory key columns.
11. Removes duplicate natural-key/quarter rows.
12. Standardizes strings and writes the Silver table.

A field can disappear from the final Silver output because it was absent from the source payload, absent from the required configuration, invalid during type conversion, or attached to a row removed by mandatory-key filtering. These causes must be distinguished during RCA.

## Silver dataset tables to joined Silver

`src/silver_job.py` aggregates measure-level tables by:

```text
facility_id + source_quarter
```

It calculates these summaries:

```text
readmissions -> avg_predicted_readmission_rate
               avg_expected_readmission_rate
               avg_excess_readmission_ratio

infections   -> avg_infection_score

complications -> avg_complication_score
                 avg_lower_estimate
                 avg_higher_estimate

hcahps       -> avg_patient_survey_star_rating
               avg_hcahps_linear_mean_value
               avg_hcahps_answer_percent
```

Those summaries are left-joined to general hospital information to create `silver.hospital_summary`.

## Joined Silver to Gold

`src/gold_job.py` reads `silver.hospital_summary` and maps source columns to risk components:

| Gold component | Silver source | Direction |
|---|---|---|
| `z_mortality` | `avg_complication_score` | Higher value increases risk |
| `z_infection` | `avg_infection_score` | Higher value increases risk |
| `z_readmission` | `avg_excess_readmission_ratio` | Higher value increases risk |
| `z_experience` | `avg_patient_survey_star_rating` | Higher value reduces risk, so sign is inverted |

The Gold table is fully recomputed and overwritten each run.

## Gold to alert

The alert is intended to find Gold rows where `early_warning_declining_trend` is true and notify recipients. The checked-in alert JSON and the visible Python table/timestamp names disagree. The live alert query, live Gold schema, and query history are required to establish whether the alert is connected correctly.

## Lineage evidence checklist

When a value or record is missing, collect evidence at each boundary:

| Boundary | Minimum check |
|---|---|
| CMS -> raw file | HTTP response, file path, file size, header, release date |
| Raw file -> Bronze | input row count, Bronze write result, new-row count, hash counts |
| Bronze -> Silver | JSON key presence, required fields, cast failures, dropped rows |
| Silver dataset -> joined Silver | facility-quarter counts before and after aggregation/join |
| Joined Silver -> Gold | input schema, input count, null metric counts, output count |
| Gold -> alert | table reference, selected columns, predicate, schedule, query result |

The model must not infer a missing record’s root cause from only the final Gold table. It should identify the first boundary where evidence changes from present/valid to absent/invalid.
