# Failure Catalog

This catalog describes what to check. A symptom is not automatically a root cause.

| Symptom | First suspected stage | Evidence to collect | Likely mechanisms | Next discriminating check |
|---|---|---|---|---|
| CMS metadata request returns an HTTP error | Ingestion | URL, status code, response body, run time | CMS outage, permission, changed endpoint | Request the same metadata URL and compare with a known-good release |
| No CSV distribution is found | Ingestion | Dataset ID and metadata payload | CMS metadata shape changed or dataset configuration is wrong | Inspect `distribution` entries and compare with `get_csv_download_url` |
| Download fails after all retries | Ingestion | Attempt logs, exception type, destination path | Network timeout, invalid URL, volume write failure | Test metadata access, download URL, and volume permissions separately |
| Raw file is missing or empty | Ingestion/raw handoff | File path, size, header, row count | Download did not complete or wrote to another path | Compare configured `raw_path` with the live file location |
| Bronze table is empty | Bronze | Raw count, table existence, write logs | Empty input, read failure, wrong path, write failure | Read the raw CSV directly and inspect table existence |
| Bronze has null `source_hash` | Bronze/quality gate | Schema and sample rows | Hash expression or source columns are invalid | Recompute a sample hash from `source_data` and metadata |
| Bronze has duplicate hashes | Bronze/quality gate | Duplicate hash values and ingestion times | Deduplication join did not work or table was manually changed | Compare incoming hashes with target hashes and inspect write mode |
| Silver reports missing required columns | Silver | Dataset, missing names, actual JSON keys, config | CMS field rename, extraction mismatch, configuration drift | Compare raw headers, `raw_field_names`, and Bronze JSON keys |
| Silver row count drops unexpectedly | Silver | Counts before/after each cleaning step | Missing mandatory keys, invalid casts, duplicate removal | Profile the rows removed at each step and group by reason |
| Numeric fields become null | Silver | Raw value, target type, cast expression, null count | Placeholder, formatting, comma, unsupported value | Compare raw strings with `column_types` and test `try_cast` |
| Date fields become null | Silver | Raw date values and target date format | CMS date-format change or malformed date | Compare values with the `MM/dd/yyyy` parser expectation |
| Joined Silver has fewer facilities than expected | Joined Silver | Counts by dataset and facility-quarter | Missing base general-info row, key mismatch, wrong quarter, aggregation loss | Compare distinct `facility_id/source_quarter` keys before each join |
| Joined Silver contains many null measure columns | Joined Silver | Null counts by measure and quarter | Dataset not released, stale dataset, key mismatch, CMS suppression | Compare release dates and facility-quarter key overlap |
| Gold cannot read Silver | Gold boundary | Table name, schema, permissions, live table existence | Wrong catalog/schema, failed Silver write, permission issue | Resolve the configured table and inspect the live schema |
| Gold metric columns are null | Gold | Input null profile, metric source columns, quarter counts | Missing measures, join loss, cast nulls | Check `METRIC_CONFIG` source columns and input null counts |
| Gold calculation fails on a window or column | Gold | Full exception and input schema | Column rename, incompatible type, malformed data | Compare live schema with `METRIC_CONFIG` and window key columns |
| Anomaly flags are unexpectedly absent | Gold/business rule | Score history, threshold, prior-quarter coverage | No prior data, threshold not crossed, rounding, missing history | Query consecutive facility-quarter scores before the flag calculation |
| Trend alerts are unexpectedly absent | Gold/business rule | Three-quarter history, score values, projection | Not enough quarters, score not strictly rising, projection below threshold | Recalculate the five trend predicates for one facility |
| Alert query returns no rows but Gold has flags | Alerting | Gold table, alert SQL, predicate, recent timestamps | Wrong table/catalog, wrong timestamp column, schedule window | Execute the exact alert query manually against the live table |
| Alert query fails on a missing column | Alerting | Query text and live schema | Alert JSON uses a stale column or table contract | Compare alert JSON with `DESCRIBE` output and Gold writer |
| Alert query returns rows but email is absent | Notification | Query result, alert run history, notification settings | Schedule, recipient, or Databricks notification configuration | Check alert execution history and notification configuration |

## Root-cause discipline

The model should identify the first boundary where an expected artifact changes from present/valid to absent/invalid. It should not call a downstream symptom the root cause when an earlier stage failed.

For each suspected mechanism, the model should state:

- Evidence supporting it
- Evidence that is missing
- A competing explanation
- One check that would distinguish the explanations
