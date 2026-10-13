# Source Index

This index maps knowledge-base topics to the repository evidence behind them.

| Topic | Primary source | Important symbols or content |
|---|---|---|
| Project purpose and high-level flow | [README.md](../README.md) | Architecture, datasets, task order, known limitations |
| Dataset registry | [config/datasets.py](../config/datasets.py) | `DATASETS`, CMS IDs, paths, keys, fields, types |
| Catalog and CMS endpoint | [config/settings.py](../config/settings.py) | `CATALOG_NAME`, schema, `CMS_METASTORE_URL_TEMPLATE` |
| CMS metadata and downloads | [pipeline/ingestion/cms_api_downloader.py](../pipeline/ingestion/cms_api_downloader.py) | `get_csv_download_url`, `download_csv_to_volume`, `get_dataset_released_date` |
| Ingestion orchestration | [src/ingest_task.py](../src/ingest_task.py) | `main` |
| Bronze preservation | [src/bronze_job.py](../src/bronze_job.py) | `read_raw_data`, `add_ingestion_metadata`, `add_source_hash`, `write_bronze_table` |
| Bronze quality | [src/quality_gate.py](../src/quality_gate.py) | `check_table`, `main`, `check_dataset_freshness` |
| Silver extraction and cleaning | [src/silver_job.py](../src/silver_job.py) | `extract_fields_from_payload`, `select_required_columns`, `replace_blank_with_null`, `cast_column_types` |
| Silver row selection | [src/silver_job.py](../src/silver_job.py) | `keep_latest_records`, `remove_null_records`, `remove_duplicates` |
| Joined Silver | [src/silver_job.py](../src/silver_job.py) | `create_joined_silver_table` |
| Silver orchestration | [src/silver_task.py](../src/silver_task.py) | `main` |
| Gold calculations | [src/gold_job.py](../src/gold_job.py) | `METRIC_CONFIG`, `WEIGHTS`, `compute_z_scores`, `compute_composite_score` |
| Gold flags | [src/gold_job.py](../src/gold_job.py) | `assign_risk_tier`, `compute_anomaly_flag`, `compute_declining_trend_alert` |
| Gold orchestration | [src/gold_task.py](../src/gold_task.py) | `main` |
| Alert configuration | [Hospital Trend Decline Alert.dbalert.json](../Hospital%20Trend%20Decline%20Alert.dbalert.json) | Schedule, query, predicate, notification |
| Exploratory evidence | [Final_demo_notebook.ipynb](../Final_demo_notebook.ipynb), [gold notebook.ipynb](../gold%20notebook.ipynb), [Silver and gold refactor.ipynb](../Silver%20and%20gold%20refactor.ipynb), [Silver Notebook.ipynb](../Silver%20Notebook.ipynb) | Analysis and demonstrations; not authoritative contracts |

## Citation format

A model should cite a repository claim with:

```text
[source-defined] src/gold_job.py :: compute_declining_trend_alert
```

A runtime claim should cite:

```text
[runtime-observed] Databricks run <run_id>, task <task_key>, observed <timestamp>
```

A table claim should cite:

```text
[runtime-observed] <catalog>.<schema>.<table>, query <query_reference>, observed <timestamp>
```

A CMS claim should cite:

```text
[runtime-observed] CMS dataset <dataset_id>, metadata request, observed <timestamp>
```

## Source status

The Markdown documents in this folder are curated explanations. They should be reviewed when source configuration, transformation logic, table schemas, or alert definitions change.
