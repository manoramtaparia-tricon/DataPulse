# Table and Column Dictionary

## Catalog and schemas

The project is designed around one catalog with three schemas:

```text
Hospital_Risk_Analysis.bronze
Hospital_Risk_Analysis.silver
Hospital_Risk_Analysis.gold
```

The current code defines the schema name locally in multiple modules. Confirm live catalog names before using this as runtime evidence.

## Bronze tables

There is one Bronze table for each configured dataset:

- `bronze.general_info`
- `bronze.readmissions`
- `bronze.infections`
- `bronze.complications`
- `bronze.hcahps`

The expected common columns are:

| Column | Type/shape | Meaning |
|---|---|---|
| `source_data` | JSON string | Complete configured source row, including explicit null keys |
| `source_released_date` | Date-like value | CMS public release date |
| `ingestion_timestamp` | Timestamp | Time captured by the pipeline |
| `source_hash` | String | SHA-256 hash of source content used for exact duplicate detection |

## Silver dataset tables

Silver has one cleaned table per dataset with fields extracted from `source_data`.

All Silver datasets are expected to have:

- Source identity fields defined by `config/datasets.py`
- `source_quarter`
- `ingestion_timestamp`
- Cleaned and typed configured fields
- A `record_pk` is described by the project README and notebook evidence, but its creation is not visible in the inspected Silver source. Verify its presence and derivation in the live schema before treating it as a code-defined contract.

Use the dataset registry for the complete field list. Do not infer a field’s business meaning from its name alone when the CMS documentation or source mapping is available.

## Joined Silver table

`Hospital_Risk_Analysis.silver.hospital_summary` is built from the five Silver dataset tables.

Its join grain is:

```text
facility_id + source_quarter
```

The general-information table is the base. Readmission, infection, complication, and HCAHPS measures are aggregated by facility and quarter and left-joined to that base.

Important derived columns include:

| Column | Source | Meaning |
|---|---|---|
| `avg_predicted_readmission_rate` | Readmissions | Average predicted readmission rate for a facility-quarter |
| `avg_expected_readmission_rate` | Readmissions | Average expected readmission rate for a facility-quarter |
| `avg_excess_readmission_ratio` | Readmissions | Average excess readmission ratio for a facility-quarter |
| `avg_infection_score` | Infections | Average infection score for a facility-quarter |
| `avg_complication_score` | Complications | Average complication score for a facility-quarter |
| `avg_lower_estimate` | Complications | Average lower estimate for a facility-quarter |
| `avg_higher_estimate` | Complications | Average higher estimate for a facility-quarter |
| `avg_patient_survey_star_rating` | HCAHPS | Average patient survey star rating for a facility-quarter |
| `avg_hcahps_linear_mean_value` | HCAHPS | Average HCAHPS linear mean for a facility-quarter |
| `avg_hcahps_answer_percent` | HCAHPS | Average HCAHPS answer percentage for a facility-quarter |

## Gold table

The Gold table is written as:

```text
Hospital_Risk_Analysis.gold.hospital_risk_report
```

Important output columns include:

| Column | Meaning |
|---|---|
| `facility_id` | Hospital identifier |
| `facility_name` | Hospital name carried from general information |
| `source_quarter` | Reporting quarter derived from the CMS release date |
| `z_mortality` | Quarter-relative standardized complication score |
| `z_infection` | Quarter-relative standardized infection score |
| `z_readmission` | Quarter-relative standardized readmission ratio |
| `z_experience` | Sign-adjusted quarter-relative patient-experience score |
| `composite_risk_score` | Weighted risk score |
| `risk_tier` | `High`, `Medium`, or `Low` |
| `prior_quarter_score` | Previous score for the same facility |
| `score_change` | Current score minus prior score |
| `anomaly_flag` | Large quarter-over-quarter score change |
| `computed_star_rating` | Project-specific rating derived from composite risk |
| `projected_next_quarter_score` | Linear projection used by the trend check |
| `early_warning_declining_trend` | Boolean early-warning condition |
| `ingestion_timestamp` | Pipeline ingestion timestamp inherited from Silver data |

Actual schemas and nullability must be checked in Databricks during an incident. The table dictionary describes the intended contract, not a substitute for the live schema.

## Alert query fields

The checked-in alert JSON selects `facility_id`, `facility_name`, `source_quarter`, `composite_risk_score`, `early_warning_declining_trend`, and `ingestion_timestamp_ist`. The visible Gold Python code does not clearly produce `ingestion_timestamp_ist`, so the alert schema and query must be verified before calling an alert failure a data failure.
