# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Build Gold Layer
# MAGIC
# MAGIC Builds the Gold tables from `clean_orders`: `daily_revenue`,
# MAGIC `customer_lifetime_value`, `product_performance`. All exclude cancelled/returned
# MAGIC orders. In a Job, depend on `02_build_silver`.

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
# MAGIC ## daily_revenue

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {FQ}.daily_revenue AS
    SELECT
        order_date,
        order_year,
        order_month,
        COUNT(*) AS total_orders,
        SUM(quantity) AS total_units_sold,
        ROUND(SUM(line_total), 2) AS total_revenue,
        ROUND(AVG(line_total), 2) AS avg_order_value,
        COUNT(DISTINCT customer_id) AS unique_customers,
        current_timestamp() AS aggregated_at
    FROM {FQ}.clean_orders
    WHERE order_status NOT IN ('cancelled', 'returned')
    GROUP BY order_date, order_year, order_month
""")
print(f"  {FQ}.daily_revenue: {spark.table(f'{FQ}.daily_revenue').count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## customer_lifetime_value

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {FQ}.customer_lifetime_value AS
    SELECT
        customer_id,
        customer_name,
        customer_city,
        customer_state,
        COUNT(*) AS total_orders,
        SUM(quantity) AS total_items_purchased,
        ROUND(SUM(line_total), 2) AS total_spent,
        ROUND(AVG(line_total), 2) AS avg_order_value,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date,
        DATEDIFF(MAX(order_date), MIN(order_date)) AS customer_tenure_days,
        COUNT(DISTINCT product_category) AS categories_purchased,
        current_timestamp() AS aggregated_at
    FROM {FQ}.clean_orders
    WHERE order_status NOT IN ('cancelled', 'returned')
    GROUP BY customer_id, customer_name, customer_city, customer_state
""")
print(f"  {FQ}.customer_lifetime_value: {spark.table(f'{FQ}.customer_lifetime_value').count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## product_performance

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {FQ}.product_performance AS
    SELECT
        product_id,
        product_name,
        product_category,
        product_brand,
        COUNT(*) AS total_orders,
        SUM(quantity) AS total_quantity_sold,
        ROUND(SUM(line_total), 2) AS total_revenue,
        ROUND(AVG(line_total), 2) AS avg_order_value,
        ROUND(AVG(unit_price), 2) AS avg_unit_price,
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT region) AS regions_sold_in,
        current_timestamp() AS aggregated_at
    FROM {FQ}.clean_orders
    WHERE order_status NOT IN ('cancelled', 'returned')
    GROUP BY product_id, product_name, product_category, product_brand
""")
print(f"  {FQ}.product_performance: {spark.table(f'{FQ}.product_performance').count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline summary

# COMMAND ----------

layers = [
    ("BRONZE", ["raw_orders", "raw_customers", "raw_products"]),
    ("SILVER", ["clean_orders"]),
    ("GOLD", ["daily_revenue", "customer_lifetime_value", "product_performance"]),
]
for layer, tbls in layers:
    print(f"  {layer}:")
    for t in tbls:
        print(f"    {t}: {spark.table(f'{FQ}.{t}').count()} rows")

# COMMAND ----------

dbutils.notebook.exit("gold_built")
