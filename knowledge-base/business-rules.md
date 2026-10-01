# Business Rules

## Reporting quarter

`source_quarter` is derived from the CMS `source_released_date`. It is a calendar-quarter label such as `2026-Q2`. The pipeline uses the release date rather than assuming that CMS releases align to a business calendar.

## Bronze duplicate rule

Bronze calculates a SHA-256 hash from the source content and skips a row when the same hash already exists in the target Bronze table.

This catches exact content duplicates. It does not prove that two rows represent the same business record and does not automatically replace a corrected CMS record that has new content.

## Silver cleaning rules

The visible cleaning path:

- Trims whitespace from strings.
- Replaces configured blank and placeholder values with null.
- Removes carriage returns, newlines, and tabs from strings.
- Uses tolerant numeric conversion.
- Uses `try_to_date` for configured dates.
- Removes rows missing mandatory identity fields.
- Keeps the latest ingestion for a natural key and source quarter.
- Removes duplicate natural-key/quarter rows.

A null value can therefore mean several different things: CMS suppression, an empty source value, a failed cast, or a missing optional field. RCA must identify which meaning is supported by evidence.

## Z-score calculation

For each configured metric, Gold calculates a z-score within the `source_quarter` population of hospitals.

```text
z = (hospital_value - quarter_mean) / quarter_standard_deviation
```

If the standard deviation is zero, the code sets the z-score to `0.0`. Missing metric values are later treated as `0.0` when building the composite score.

## Composite risk score

The configured weights are:

```text
composite_risk_score =
    0.35 * z_mortality
  + 0.25 * z_infection
  + 0.25 * z_readmission
  + 0.15 * z_experience
```

The patient-experience component is sign-inverted because higher patient survey ratings represent better experience and lower risk.

This is a project-specific score. It is not a reproduction of the official CMS star-rating methodology.

## Risk tiers

The current thresholds in `src/gold_job.py` are:

```text
composite_risk_score >=  1.0 -> High
composite_risk_score <= -1.0 -> Low
otherwise                    -> Medium
```

The thresholds are applied after the composite score is calculated.

## Anomaly flag

The anomaly flag compares a facility’s current composite score with its immediately prior quarter:

```text
abs(current_score - prior_quarter_score) > 1.5 -> anomaly_flag = true
```

The first available quarter for a facility has no prior score and is not flagged.

## Early-warning declining trend

The code treats a rising risk score as declining quality. The flag requires:

1. At least three ranked quarters for the facility.
2. The current score is greater than the previous score.
3. The previous score is greater than the score two quarters earlier.
4. The current score is still below the High threshold.
5. A simple linear projection reaches or exceeds the High threshold next quarter.

The projection is based on the average increase across the two most recent changes.

## Computed star rating

The project also derives a bounded rating from the composite score:

```text
computed_star_rating = round(clamp(3.0 - composite_risk_score, 1.0, 5.0))
```

This computed rating is independent of the CMS-provided `hospital_overall_rating`.

## Rounding

The Gold job rounds continuous output columns, including z-scores, composite score, score change, and projected score, before writing the final table.

## Rules that require operational verification

- The constant `CMS_ALERT_THRESHOLD = 2.5` is present in the Gold source but is not used in the visible calculation flow.
- The exact nullability and output schema should be checked in the live Gold table.
- The alert query uses names that do not match the visible Gold writer and must be reconciled.
- The freshness helper’s SQL should be tested before its result is used as evidence.
