# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Build Silver Layer
# MAGIC
# MAGIC Builds `clean_orders` from the Bronze tables: joins orders + customers + products,
# MAGIC deduplicates on `order_id`, and drops invalid quantity/region/dates, orphan
# MAGIC references and non-positive prices. In a Job, depend on `01_generate_bronze`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("catalog", "test_catalog", "Catalog")
dbutils.widgets.text("schema", "default", "Schema")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
FQ = f"{CATALOG}.{SCHEMA}"
print(f"Target: {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## clean_orders

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {FQ}.clean_orders AS
    SELECT
        o.order_id,
        o.customer_id,
        c.first_name,
        c.last_name,
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
        c.city AS customer_city,
        c.state AS customer_state,
        o.product_id,
        p.product_name,
        p.category AS product_category,
        p.brand AS product_brand,
        o.quantity,
        p.unit_price,
        ROUND(o.quantity * p.unit_price, 2) AS line_total,
        TRY_CAST(o.order_date AS DATE) AS order_date,
        MONTH(TRY_CAST(o.order_date AS DATE)) AS order_month,
        YEAR(TRY_CAST(o.order_date AS DATE)) AS order_year,
        o.order_status,
        o.payment_method,
        o.region,
        o.source_system,
        current_timestamp() AS processed_at
    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY ingested_at DESC) AS rn
        FROM {FQ}.raw_orders
        WHERE quantity IS NOT NULL
          AND quantity > 0
          AND region IS NOT NULL
    ) o
    INNER JOIN {FQ}.raw_customers c ON o.customer_id = c.customer_id
    INNER JOIN {FQ}.raw_products p ON o.product_id = p.product_id
    WHERE o.rn = 1
      AND TRY_CAST(o.order_date AS DATE) IS NOT NULL
      AND TRY_CAST(o.order_date AS DATE) <= CURRENT_DATE()
      AND p.unit_price > 0
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify and drop-off

# COMMAND ----------

bronze_count = spark.table(f"{FQ}.raw_orders").count()
silver_count = spark.table(f"{FQ}.clean_orders").count()
drop_pct = round((1 - silver_count / bronze_count) * 100, 1) if bronze_count else 0.0

print(f"  {FQ}.clean_orders: {silver_count} rows")
print(f"  Bronze → Silver drop-off: {bronze_count} → {silver_count} ({drop_pct}% filtered)")

# COMMAND ----------

dbutils.notebook.exit(f"silver_built rows={silver_count}")
