# Datasets and Contracts

## Dataset registry

The authoritative dataset registry is `config/datasets.py`. It defines the CMS dataset ID, raw path, table names, natural keys, mandatory columns, required columns, raw field names, and type casts.

| Dataset | CMS ID | Natural key | Mandatory columns | Silver table |
|---|---|---|---|---|
| General hospital information | `xubh-q36u` | `facility_id` | `facility_id`, `facility_name` | `Hospital_Risk_Analysis.silver.general_info` |
| Readmissions | `9n3s-kdb3` | `facility_id`, `measure_name` | `facility_id`, `measure_name` | `Hospital_Risk_Analysis.silver.readmissions` |
| Healthcare-associated infections | `77hc-ibv8` | `facility_id`, `measure_id` | `facility_id`, `measure_id` | `Hospital_Risk_Analysis.silver.infections` |
| Complications and deaths | `ynj2-r877` | `facility_id`, `measure_id` | `facility_id`, `measure_id` | `Hospital_Risk_Analysis.silver.complications` |
| HCAHPS patient experience | `dgck-syfz` | `facility_id`, `hcahps_measure_id` | `facility_id`, `hcahps_measure_id` | `Hospital_Risk_Analysis.silver.hcahps` |

The catalog and schema names above come from the checked-in configuration and module constants. Confirm them against the live Unity Catalog before using them in an incident report.

## Common metadata

The Bronze layer adds these fields to every dataset:

| Field | Meaning |
|---|---|
| `source_data` | JSON representation of the raw CSV row |
| `source_released_date` | CMS release date returned by the metadata endpoint |
| `ingestion_timestamp` | Time the pipeline captured the row, converted to Asia/Kolkata in Bronze |
| `source_hash` | SHA-256 content fingerprint used for exact-row deduplication |

`source_hash` is not a business key. It identifies identical content for ingestion purposes; it does not identify a hospital or reporting period.

## General information

The general-information dataset supplies facility identity and CMS overall rating fields. It includes identifiers, name, address, state, ownership, emergency-service information, CMS overall rating, and measure-count fields.

The `facility_id` is the anchor used to join the general information record to aggregated measures in `silver.hospital_summary`.

## Readmissions

Important fields include:

- `facility_id`
- `measure_name`
- `number_of_discharges`
- `number_of_readmissions`
- `predicted_readmission_rate`
- `expected_readmission_rate`
- `excess_readmission_ratio`
- `start_date`
- `end_date`
- `source_quarter`

The joined Silver table calculates `avg_predicted_readmission_rate`, `avg_expected_readmission_rate`, and `avg_excess_readmission_ratio` by facility and quarter.

## Infections

Important fields include `facility_id`, `measure_id`, `measure_name`, `compared_to_national`, `score`, date fields, and `source_quarter`.

The joined Silver table calculates `avg_infection_score` by facility and quarter.

## Complications and deaths

Important fields include `facility_id`, `measure_id`, `measure_name`, `compared_to_national`, `denominator`, `score`, `lower_estimate`, `higher_estimate`, date fields, and `source_quarter`.

The joined Silver table calculates `avg_complication_score`, `avg_lower_estimate`, and `avg_higher_estimate` by facility and quarter.

## HCAHPS

Important fields include `facility_id`, `hcahps_measure_id`, question and answer descriptions, patient survey star rating, linear mean, answer percent, response rate, date fields, and `source_quarter`.

The joined Silver table calculates `avg_patient_survey_star_rating`, `avg_hcahps_linear_mean_value`, and `avg_hcahps_answer_percent` by facility and quarter.

## Contract checks for an incident

For every dataset involved in a failed run, compare:

1. CMS metadata and current CSV headers
2. `raw_field_names` in `config/datasets.py`
3. `required_columns` in `config/datasets.py`
4. `mandatory_columns` and `natural_key_cols`
5. `column_types`
6. Actual Bronze JSON keys
7. Actual Silver schema
8. Row counts before and after cleaning
9. The presence of `facility_id` and `source_quarter`

A missing required field should be reported as a contract mismatch. A missing optional field or a CMS placeholder should not automatically be called a pipeline defect.
