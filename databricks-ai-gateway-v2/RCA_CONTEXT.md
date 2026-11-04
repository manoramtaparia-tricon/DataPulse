# Root Cause Analysis (RCA) Context

This document is loaded **only** for the RCA step, on top of `AGENT_CONTEXT.md` and the
pipeline notebooks. It tells the agent how the pipeline is executed, which read-only
evidence sources exist, and how to establish *why* a tracked record is missing or stuck.

RCA always starts from a completed tracking result: the entity, the layers it was
found in, and the first layer where it is absent. RCA does not re-track the entity; it
explains the gap.

---

## Pipeline Execution

One Databricks Job (Workflows) runs three notebook tasks in sequence on a schedule
(see `databricks_notebooks/JOBS.md`):

| Task key | Notebook | Depends on | Writes | Write mode |
|----------|----------|------------|--------|------------|
| `bronze` | `01_generate_bronze` | — | `raw_orders` (append), `raw_customers` / `raw_products` (seeded once) | append / overwrite-if-empty |
| `silver` | `02_build_silver` | `bronze` | `clean_orders` | `CREATE OR REPLACE` |
| `gold`   | `03_build_gold`   | `silver` | `daily_revenue`, `customer_lifetime_value`, `product_performance` | `CREATE OR REPLACE` |

Consequences for RCA:

- If `silver` fails, is skipped, or has not run since a record was ingested, that record is
  absent from `clean_orders` and from every Gold table, even though it is valid.
- If `gold` fails or has not run since the last Silver build, Gold lags Silver.
- `raw_customers` and `raw_products` are seeded only on the first run. A customer or
  product id not present there will never appear, regardless of how many runs succeed.
- Task-level error messages and stack traces are **not** available through SQL (known gap).
  The `termination_code` is the most detailed failure signal reachable here.

---

## Read-only Evidence Sources

Use them in this order: cheapest and most decisive first.

### 1. Row-level data checks (always available)

Query the Bronze rows for the entity and evaluate each drop rule from
"Transformation Rules & Drop Conditions" in `AGENT_CONTEXT.md`. A single query that labels
each row with the first rule it fails is usually decisive. Template (adapt the `WHERE` to
the entity's key):

```sql
SELECT r.order_id, r.customer_id, r.product_id, r.quantity, r.region, r.order_date,
       r.order_status, r.ingested_at,
       CASE
         WHEN r.quantity IS NULL OR r.quantity <= 0            THEN 'INVALID_QUANTITY'
         WHEN r.region IS NULL                                  THEN 'NULL_REGION'
         WHEN c.customer_id IS NULL                             THEN 'ORPHAN_CUSTOMER'
         WHEN p.product_id IS NULL                              THEN 'ORPHAN_PRODUCT'
         WHEN TRY_CAST(r.order_date AS DATE) IS NULL            THEN 'INVALID_DATE'
         WHEN TRY_CAST(r.order_date AS DATE) > CURRENT_DATE()   THEN 'FUTURE_DATE'
         WHEN p.unit_price <= 0                                 THEN 'NON_POSITIVE_PRICE'
         ELSE 'PASSES_RULES'
       END AS rule_check
FROM test_catalog.bronze.raw_orders r
LEFT JOIN test_catalog.bronze.raw_customers c ON r.customer_id = c.customer_id
LEFT JOIN test_catalog.bronze.raw_products  p ON r.product_id  = p.product_id
WHERE r.customer_id = <id>
ORDER BY r.order_id, r.ingested_at DESC
```

Rows labelled `PASSES_RULES` that are still absent from Silver point to deduplication
(a newer version of the same `order_id` failed a later rule; see the dedup subtlety in
`AGENT_CONTEXT.md`) or to a stale or failed pipeline run (sources 2–3).

For a **customer** or **product** with zero rows in `raw_orders`, the explanation is "no
orders exist". This is expected behaviour, not a pipeline defect.

`FUTURE_DATE` is evaluated against the date of the **last build**, not today. A date that
was in the future at `MAX(processed_at)` will pass on the next successful run.

### 2. Layer freshness (always available)

```sql
SELECT MAX(processed_at)  AS last_silver_build FROM test_catalog.silver.clean_orders;
SELECT MAX(aggregated_at) AS last_gold_build   FROM test_catalog.gold.customer_lifetime_value;
```

If the entity's Bronze `ingested_at` is **later** than the downstream table's last build,
the record has not been processed yet (stale or failed downstream run). Each table is
fully rebuilt, so every row in a table shares roughly the same audit timestamp.

### 3. Delta table history (usually available)

`DESCRIBE HISTORY <fully-qualified table> LIMIT 5` returns each table's recent commits:
`version`, `timestamp`, `operation` (e.g. `CREATE OR REPLACE TABLE AS SELECT`, `WRITE`),
`job` (job id / run id when written by a Job), and `operationMetrics` (e.g.
`numOutputRows`). Use it to see when Silver/Gold were last rewritten, by which job run,
and whether the row count changed unexpectedly.

### 4. Databricks system tables (may be unavailable)

These require system tables to be enabled and granted. If a query errors with a
permission or "table not found" error, record the source as **unavailable** and continue.
Never treat an unavailable source as evidence that nothing failed.

- `system.lakeflow.jobs`: job definitions (SCD2; latest row per `job_id` by `change_time`).
  Columns: `job_id`, `name`, `change_time`, `delete_time`.
- `system.lakeflow.job_run_timeline`: job-level runs. Columns: `job_id`, `run_id`,
  `period_start_time`, `period_end_time`, `trigger_type`, `result_state`, `termination_code`.
- `system.lakeflow.job_task_run_timeline`: task-level runs. Columns: `job_id`, `job_run_id`,
  `run_id` (task run), `task_key`, `period_start_time`, `period_end_time`, `result_state`,
  `termination_code`.

Long runs are split into several time-slice rows; `result_state` is set on the final slice.
`result_state` values: `SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED`, `TIMED_OUT`, `ERROR`,
`BLOCKED`, or `NULL` while running.

Recent task runs of this pipeline (the job is identified by its task keys):

```sql
SELECT job_id, job_run_id, task_key,
       MIN(period_start_time)                   AS started_at,
       MAX(period_end_time)                     AS ended_at,
       MAX_BY(result_state, period_end_time)     AS result_state,
       MAX_BY(termination_code, period_end_time) AS termination_code
FROM system.lakeflow.job_task_run_timeline
WHERE task_key IN ('bronze', 'silver', 'gold')
  AND period_start_time >= current_timestamp() - INTERVAL 7 DAYS
GROUP BY job_id, job_run_id, task_key
ORDER BY started_at DESC
LIMIT 30
```

If several `job_id`s match, prefer the one that has all three task keys, and resolve its
name with `system.lakeflow.jobs`.

---

## Diagnostic Path by Gap

| Gap (from tracking) | Check first | Then |
|---------------------|-------------|------|
| Absent in Bronze source | Id range / max id in the Bronze table (`MAX(customer_id)`, `MAX(order_id)`) | `bronze` task runs and `raw_*` history: was it never generated or never loaded? |
| Bronze → Silver | Row-level rule check (source 1) | Dedup versions, then Silver freshness vs `ingested_at`, then `silver` task runs |
| Silver → Gold | `order_status` of the entity's `clean_orders` rows (all `cancelled`/`returned`?) | Gold freshness vs Silver `processed_at`, then `gold` task runs |

Stop as soon as one check fully explains the gap **and** the run evidence does not contradict it.
Example: every order fails a rule. If no rule explains it, move to freshness and runs.

---

## Failure Categories

Use exactly one of these for the primary cause:

| Category | Meaning | Defect? |
|----------|---------|---------|
| `SOURCE_MISSING` | Never ingested into its Bronze source table | Depends on the source |
| `NO_UPSTREAM_ACTIVITY` | Entity exists but has nothing to flow downstream (e.g. a customer with no orders) | No, expected |
| `DATA_QUALITY_FILTER` | Removed by a validation rule (quantity, region, invalid/future date, non-positive price) | Yes, data quality |
| `ORPHAN_REFERENCE` | Dropped by an INNER JOIN to a missing customer/product | Yes, referential integrity |
| `DEDUP_SUPERSEDED` | The latest version of the `order_id` failed a post-dedup rule, so the whole order was dropped | Yes, data quality or design |
| `BUSINESS_RULE_EXCLUSION` | Excluded by design (cancelled/returned orders not in Gold) | No, expected |
| `PIPELINE_NOT_RUN` | Downstream not rebuilt since the record was ingested | Possibly (schedule) |
| `PIPELINE_FAILURE` | The responsible task failed, was skipped, cancelled, or timed out | Yes, operational |
| `UNKNOWN` | Evidence does not establish a cause | n/a |

---

## Evidence Discipline

- Every claim must cite a query result or a documented rule. Do not invent run ids,
  timestamps, or error messages.
- `HIGH` confidence: a query result directly shows the mechanism (e.g. every order row
  fails a named rule), and no evidence contradicts it.
- `MEDIUM` confidence: the failing transition is clear, but one more check is needed to pin down
  the mechanism.
- `LOW` confidence: based mainly on documentation or symptoms; key evidence was unavailable.
- Report a cause as identified only at `HIGH` confidence; otherwise give ranked hypotheses.
- Report the fields that explain the drop (quantity, region, order_date, order_status,
  ids, timestamps). Never output personal data such as names, emails, phones, or addresses.
- RCA is diagnosis only. It never modifies data, reruns jobs, or claims a fix was applied.
  Remediation is a separate, later step.
