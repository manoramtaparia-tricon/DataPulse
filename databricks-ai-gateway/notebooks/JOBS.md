# Databricks Notebooks

Three import-ready notebooks, one per medallion layer, that generate fresh synthetic
data and build the Bronze, Silver and Gold tables on an attached cluster using `spark`
and `spark.sql` (no SQL connector or token needed).

| Notebook | Does | Writes |
|----------|------|--------|
| `01_generate_bronze.py` | Generates randomized data and loads Bronze | `raw_orders`, `raw_customers`, `raw_products` |
| `02_build_silver.py` | Joins, validates and deduplicates into Silver | `clean_orders` |
| `03_build_gold.py` | Aggregates Silver into Gold | `daily_revenue`, `customer_lifetime_value`, `product_performance` |

Data is different on every run: no random seed, and order/signup dates are relative to
the run date. Catalog, schema and row counts are widget parameters set on the Job task.

Each run **appends** a new batch of orders, so `raw_orders` grows over time (order_id
continues from the current maximum). Customers and products are seeded once on the first
run and left as-is afterwards, so they are not duplicated. Silver and Gold are rebuilt
each run from the full, accumulated Bronze, so they grow along with it and stay correct.

## Import into Databricks
Workspace > Import > File, and select each `.py` (they carry the
`# Databricks notebook source` header and import as notebooks). Or point a Repos / Git
folder at this repository.

## Wire up the Job (UI)
1. Workflows > Create Job.
2. Task `bronze`: Notebook `01_generate_bronze`, attach your cluster.
3. Task `silver`: Notebook `02_build_silver`, depends on `bronze`, same cluster.
4. Task `gold`: Notebook `03_build_gold`, depends on `silver`, same cluster.
5. Parameters (optional; defaults shown): `catalog=test_catalog`, `schema=default`,
   `num_customers=200`, `num_orders=5000` (the last two apply to the bronze task only).
6. Add a schedule trigger and save.

## How data accumulates
- **Bronze orders** append each run (`raw_orders` grows; order_id continues from the max).
- **Bronze customers/products** are seeded once; later runs leave them unchanged. To
  reseed them, drop the tables and rerun.
- **Silver and Gold** use `CREATE OR REPLACE`, recomputing from the full Bronze every run.
  They are not independent snapshots — they reflect all accumulated Bronze data, so they
  grow with it while staying correct (no double-counting of aggregates).
