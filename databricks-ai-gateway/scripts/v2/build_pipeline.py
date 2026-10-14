"""Build Silver and Gold tables from Bronze layer using separate schemas."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
load_dotenv()

from src.db_connection import run_query

CATALOG = "test_catalog"
BRONZE = f"{CATALOG}.bronze"
SILVER = f"{CATALOG}.silver"
GOLD = f"{CATALOG}.gold"


def build_silver():
    print("=== SILVER LAYER ===\n")

    print("Building clean_orders...")
    run_query(f"DROP TABLE IF EXISTS {SILVER}.clean_orders")
    run_query(f"""
        CREATE TABLE {SILVER}.clean_orders AS
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
            FROM {BRONZE}.raw_orders
            WHERE quantity IS NOT NULL
              AND quantity > 0
              AND region IS NOT NULL
        ) o
        INNER JOIN {BRONZE}.raw_customers c ON o.customer_id = c.customer_id
        INNER JOIN {BRONZE}.raw_products p ON o.product_id = p.product_id
        WHERE o.rn = 1
          AND TRY_CAST(o.order_date AS DATE) IS NOT NULL
          AND TRY_CAST(o.order_date AS DATE) <= CURRENT_DATE()
          AND p.unit_price > 0
    """)
    _, rows = run_query(f"SELECT COUNT(*) FROM {SILVER}.clean_orders")
    print(f"  {SILVER}.clean_orders: {rows[0][0]} rows\n")


def build_gold():
    print("=== GOLD LAYER ===\n")

    print("Building daily_revenue...")
    run_query(f"DROP TABLE IF EXISTS {GOLD}.daily_revenue")
    run_query(f"""
        CREATE TABLE {GOLD}.daily_revenue AS
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
        FROM {SILVER}.clean_orders
        WHERE order_status NOT IN ('cancelled', 'returned')
        GROUP BY order_date, order_year, order_month
    """)
    _, rows = run_query(f"SELECT COUNT(*) FROM {GOLD}.daily_revenue")
    print(f"  {GOLD}.daily_revenue: {rows[0][0]} rows")

    print("Building customer_lifetime_value...")
    run_query(f"DROP TABLE IF EXISTS {GOLD}.customer_lifetime_value")
    run_query(f"""
        CREATE TABLE {GOLD}.customer_lifetime_value AS
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
        FROM {SILVER}.clean_orders
        WHERE order_status NOT IN ('cancelled', 'returned')
        GROUP BY customer_id, customer_name, customer_city, customer_state
    """)
    _, rows = run_query(f"SELECT COUNT(*) FROM {GOLD}.customer_lifetime_value")
    print(f"  {GOLD}.customer_lifetime_value: {rows[0][0]} rows")

    print("Building product_performance...")
    run_query(f"DROP TABLE IF EXISTS {GOLD}.product_performance")
    run_query(f"""
        CREATE TABLE {GOLD}.product_performance AS
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
        FROM {SILVER}.clean_orders
        WHERE order_status NOT IN ('cancelled', 'returned')
        GROUP BY product_id, product_name, product_category, product_brand
    """)
    _, rows = run_query(f"SELECT COUNT(*) FROM {GOLD}.product_performance")
    print(f"  {GOLD}.product_performance: {rows[0][0]} rows")


def print_summary():
    print("\n=== PIPELINE SUMMARY ===\n")
    tables = [
        ("BRONZE", BRONZE, ["raw_orders", "raw_customers", "raw_products"]),
        ("SILVER", SILVER, ["clean_orders"]),
        ("GOLD", GOLD, ["daily_revenue", "customer_lifetime_value", "product_performance"]),
    ]
    for layer, schema, tbls in tables:
        print(f"  {layer} ({schema}):")
        for t in tbls:
            _, rows = run_query(f"SELECT COUNT(*) FROM {schema}.{t}")
            print(f"    {t}: {rows[0][0]} rows")

    _, bronze = run_query(f"SELECT COUNT(*) FROM {BRONZE}.raw_orders")
    _, silver = run_query(f"SELECT COUNT(*) FROM {SILVER}.clean_orders")
    bronze_count = bronze[0][0]
    silver_count = silver[0][0]
    drop_pct = round((1 - silver_count / bronze_count) * 100, 1)
    print(f"\n  Bronze → Silver drop-off: {bronze_count} → {silver_count} ({drop_pct}% filtered)")


if __name__ == "__main__":
    build_silver()
    build_gold()
    print_summary()
    print("\nPipeline built successfully!")
