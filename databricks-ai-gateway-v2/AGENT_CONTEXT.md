# E-Commerce Data Platform — Databricks Medallion Architecture

## Project Overview

This project builds an end-to-end data engineering platform for an e-commerce business using Databricks. It processes raw transactional data through a **Medallion Architecture** (Bronze → Silver → Gold) to produce business-ready analytics.

An **AI agent** powered by Google Gemini understands the system by reading this documentation and the pipeline code. It traces and investigates data across the Bronze, Silver, and Gold layers — checking whether an entity flows through the layers, where it was dropped, and why — by querying the Databricks tables directly (SELECT only). It learns the architecture, tables, keys, and data flow entirely from this document.

### Business Problem

The e-commerce business needs a unified data platform that:
- Ingests raw transactional data (orders, customers, products) into a raw landing zone
- Cleans and enriches the data into a reliable, queryable format
- Produces aggregated business metrics for revenue tracking, customer analytics, and product performance
- Allows non-technical stakeholders to ask questions about the data in plain English

### Key Objectives

1. Build a scalable medallion pipeline that handles raw data ingestion, cleaning, and aggregation
2. Maintain full data lineage so any metric can be traced back to its source
3. Provide an AI-powered interface for exploring and investigating the data

---

## Architecture

```mermaid
graph LR
    subgraph Bronze Layer
        B1[raw_orders]
        B2[raw_customers]
        B3[raw_products]
    end

    subgraph Silver Layer
        SV[clean_orders]
    end

    subgraph Gold Layer
        G1[daily_revenue]
        G2[customer_lifetime_value]
        G3[product_performance]
    end

    B1 & B2 & B3 --> SV
    SV --> G1 & G2 & G3
```

---

## Data Flow

```mermaid
flowchart TD
    subgraph Bronze["Bronze — Raw Ingestion"]
        RO[raw_orders<br/>Raw order transactions as ingested]
        RC[raw_customers<br/>Raw customer records as ingested]
        RP[raw_products<br/>Raw product catalog as ingested]
    end

    subgraph Silver["Silver — Cleaned & Enriched"]
        CO[clean_orders<br/>Validated orders joined with<br/>customer and product details]
    end

    subgraph Gold["Gold — Business Metrics"]
        DR[daily_revenue<br/>Revenue aggregated by day]
        CLV[customer_lifetime_value<br/>Spend and behavior per customer]
        PP[product_performance<br/>Sales metrics per product]
    end

    RO -->|JOIN + validate| CO
    RC -->|JOIN| CO
    RP -->|JOIN| CO
    CO -->|aggregate by date| DR
    CO -->|aggregate by customer| CLV
    CO -->|aggregate by product| PP
```

---

## Tables

### Bronze Layer

Raw data ingested as-is from source systems. No cleaning or validation is applied.

- **`test_catalog.default.raw_orders`** — Order transactions from all source systems
- **`test_catalog.default.raw_customers`** — Customer records
- **`test_catalog.default.raw_products`** — Product catalog

### Silver Layer

Cleaned, validated, and enriched data. Multiple Bronze sources are joined and transformed here.

- **`test_catalog.default.clean_orders`** — Enriched order data combining orders, customers, and products. Pipeline: `scripts/initial_load/build_pipeline.py`

### Gold Layer

Business-ready aggregated metrics derived from the Silver layer.

- **`test_catalog.default.daily_revenue`** — Revenue and order metrics aggregated by day
- **`test_catalog.default.customer_lifetime_value`** — Customer spend, tenure, and behavior metrics
- **`test_catalog.default.product_performance`** — Product sales, revenue, and reach metrics

Pipeline for all Gold tables: `scripts/initial_load/build_pipeline.py`

---

## Table & Column Reference

Complete schema for every table, at table and column level. The agent uses this section for all table and column metadata and does not run `DESCRIBE TABLE` or `SHOW TABLES` to discover structure.

Notes:
- Data types are Spark SQL types. Databricks does not enforce `PRIMARY KEY` / `FOREIGN KEY` constraints here; the "Key" column documents the **logical** keys and relationships.
- `COUNT`/`SUM` of integer columns return `BIGINT`; `ROUND(...)`, `AVG(...)`, and sums of `DOUBLE` columns return `DOUBLE`.

### Bronze

#### `test_catalog.default.raw_orders`
Raw order transactions as received from source systems. No cleaning applied — may contain duplicates, NULLs, invalid dates, and orphan references. **Grain:** one row per ingested order record (duplicates possible).

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `order_id` | INT | PK (not unique in Bronze — duplicates exist) | Order identifier |
| `customer_id` | INT | FK → `raw_customers.customer_id` | Ordering customer (may reference a non-existent customer, 900–999) |
| `product_id` | INT | FK → `raw_products.product_id` | Ordered product (may reference a non-existent product, 900–999) |
| `quantity` | INT | | Units ordered (may be NULL or ≤ 0 in raw) |
| `order_date` | STRING | | Order date as text `YYYY-MM-DD` (may be `'INVALID'` or a future date) |
| `order_status` | STRING | | One of `completed`, `shipped`, `processing`, `cancelled`, `returned` |
| `payment_method` | STRING | | One of `credit_card`, `debit_card`, `paypal`, `bank_transfer`, `gift_card` |
| `source_system` | STRING | | Ingestion source: `web_app`, `mobile_app`, `pos_terminal`, `partner_api` |
| `region` | STRING | | One of `East`, `West`, `North`, `South`, `Central` (may be NULL) |
| `ingested_at` | TIMESTAMP | | When the row was ingested into Bronze (audit timestamp) |

#### `test_catalog.default.raw_customers`
Raw customer master records. **Grain:** one row per customer.

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `customer_id` | INT | PK | Customer identifier (1–200) |
| `first_name` | STRING | | Customer first name |
| `last_name` | STRING | | Customer last name |
| `email` | STRING | | Email address (may be NULL, ~5%) |
| `phone` | STRING | | Phone number (may be NULL, ~3%) |
| `city` | STRING | | City |
| `state` | STRING | | US state (2-letter code) |
| `country` | STRING | | Country (always `US`) |
| `signup_date` | STRING | | Signup date as text `YYYY-MM-DD` |
| `source_system` | STRING | | Acquisition source: `web_app`, `mobile_app`, `pos_terminal`, `partner_api` |
| `ingested_at` | TIMESTAMP | | When the row was ingested into Bronze (audit timestamp) |

#### `test_catalog.default.raw_products`
Raw product catalog. **Grain:** one row per product.

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `product_id` | INT | PK | Product identifier (1–50) |
| `product_name` | STRING | | Product name |
| `category` | STRING | | One of `Electronics`, `Clothing`, `Home & Kitchen`, `Sports`, `Books`, `Beauty` |
| `brand` | STRING | | Brand name |
| `unit_price` | DOUBLE | | Price per unit (may be 0 or negative in raw, ~4%) |
| `weight_kg` | DOUBLE | | Product weight in kilograms |
| `source_system` | STRING | | Ingestion source |
| `ingested_at` | TIMESTAMP | | When the row was ingested into Bronze (audit timestamp) |

### Silver

#### `test_catalog.default.clean_orders`
Validated, deduplicated, enriched order lines — `raw_orders` joined to `raw_customers` and `raw_products`. **Grain:** one row per valid `order_id` (deduplicated to the latest ingestion). Built by `scripts/initial_load/build_pipeline.py`.

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `order_id` | INT | PK (unique after dedup) | Order identifier |
| `customer_id` | INT | FK → `raw_customers.customer_id` | Ordering customer |
| `first_name` | STRING | | Customer first name (from `raw_customers`) |
| `last_name` | STRING | | Customer last name (from `raw_customers`) |
| `customer_name` | STRING | | `first_name` + `' '` + `last_name` |
| `customer_city` | STRING | | Customer city (from `raw_customers.city`) |
| `customer_state` | STRING | | Customer state (from `raw_customers.state`) |
| `product_id` | INT | FK → `raw_products.product_id` | Ordered product |
| `product_name` | STRING | | Product name (from `raw_products`) |
| `product_category` | STRING | | Product category (from `raw_products.category`) |
| `product_brand` | STRING | | Product brand (from `raw_products.brand`) |
| `quantity` | INT | | Units ordered (always > 0 here) |
| `unit_price` | DOUBLE | | Price per unit (always > 0 here, from `raw_products`) |
| `line_total` | DOUBLE | | `ROUND(quantity * unit_price, 2)` — revenue for this line |
| `order_date` | DATE | | Order date (valid, ≤ current date) |
| `order_month` | INT | | Month of `order_date` (1–12) |
| `order_year` | INT | | Year of `order_date` |
| `order_status` | STRING | | Order status (carried from Bronze) |
| `payment_method` | STRING | | Payment method (carried from Bronze) |
| `region` | STRING | | Region (carried from Bronze, non-NULL here) |
| `source_system` | STRING | | Source system (carried from Bronze) |
| `processed_at` | TIMESTAMP | | When this Silver row was built (audit timestamp) |

### Gold

#### `test_catalog.default.daily_revenue`
Revenue and order metrics aggregated by day, from `clean_orders` (excludes `cancelled`/`returned`). **Grain:** one row per `order_date`.

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `order_date` | DATE | PK | The day being summarized |
| `order_year` | INT | | Year of `order_date` |
| `order_month` | INT | | Month of `order_date` (1–12) |
| `total_orders` | BIGINT | | Count of orders that day |
| `total_units_sold` | BIGINT | | Sum of `quantity` that day |
| `total_revenue` | DOUBLE | | Sum of `line_total` that day |
| `avg_order_value` | DOUBLE | | Average `line_total` that day |
| `unique_customers` | BIGINT | | Distinct customers that day |
| `aggregated_at` | TIMESTAMP | | When this Gold row was built (audit timestamp) |

#### `test_catalog.default.customer_lifetime_value`
Per-customer spend, tenure, and behavior, from `clean_orders` (excludes `cancelled`/`returned`). **Grain:** one row per `customer_id`.

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `customer_id` | INT | PK | Customer identifier |
| `customer_name` | STRING | | Customer full name |
| `customer_city` | STRING | | Customer city |
| `customer_state` | STRING | | Customer state |
| `total_orders` | BIGINT | | Lifetime order count |
| `total_items_purchased` | BIGINT | | Lifetime sum of `quantity` |
| `total_spent` | DOUBLE | | Lifetime sum of `line_total` |
| `avg_order_value` | DOUBLE | | Average `line_total` across orders |
| `first_order_date` | DATE | | Earliest `order_date` |
| `last_order_date` | DATE | | Latest `order_date` |
| `customer_tenure_days` | INT | | Days between first and last order |
| `categories_purchased` | BIGINT | | Distinct product categories purchased |
| `aggregated_at` | TIMESTAMP | | When this Gold row was built (audit timestamp) |

#### `test_catalog.default.product_performance`
Per-product sales, revenue, and reach, from `clean_orders` (excludes `cancelled`/`returned`). **Grain:** one row per `product_id`.

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| `product_id` | INT | PK | Product identifier |
| `product_name` | STRING | | Product name |
| `product_category` | STRING | | Product category |
| `product_brand` | STRING | | Product brand |
| `total_orders` | BIGINT | | Number of orders containing this product |
| `total_quantity_sold` | BIGINT | | Total units sold |
| `total_revenue` | DOUBLE | | Sum of `line_total` for this product |
| `avg_order_value` | DOUBLE | | Average `line_total` for this product |
| `avg_unit_price` | DOUBLE | | Average `unit_price` for this product |
| `unique_customers` | BIGINT | | Distinct customers who bought it |
| `regions_sold_in` | BIGINT | | Distinct regions it sold in |
| `aggregated_at` | TIMESTAMP | | When this Gold row was built (audit timestamp) |

---

## Data Lineage

```mermaid
graph TD
    RO[raw_orders] -->|customer_id| RC[raw_customers]
    RO -->|product_id| RP[raw_products]

    RO --> CO[clean_orders]
    RC -->|INNER JOIN| CO
    RP -->|INNER JOIN| CO

    CO --> DR[daily_revenue]
    CO --> CLV[customer_lifetime_value]
    CO --> PP[product_performance]
```

To trace any Gold metric back to its source, follow the lineage through `clean_orders` back to the Bronze tables. The transformation logic is defined in `scripts/initial_load/build_pipeline.py`.

---

## Join Keys

All joins between tables use these keys.

| Relationship                        | Key column    | Join type   |
|-------------------------------------|---------------|-------------|
| `raw_orders` → `raw_customers`      | `customer_id` | INNER JOIN  |
| `raw_orders` → `raw_products`       | `product_id`  | INNER JOIN  |
| `clean_orders` → `customer_lifetime_value` | `customer_id` | aggregation |
| `clean_orders` → `product_performance`     | `product_id`  | aggregation |
| `clean_orders` → `daily_revenue`           | `order_date`  | aggregation |

> **ID format:** `customer_id`, `order_id`, and `product_id` are integers. Do not quote them in SQL.

---

## Entity Lineage & Tracking

Each business entity flows through a specific set of tables. To check whether an entity is present across the layers, query these tables in order (Bronze → Silver → Gold):

| Entity   | Key column    | Bronze          | Silver         | Gold                       |
|----------|---------------|-----------------|----------------|----------------------------|
| Customer | `customer_id` | `raw_customers` | `clean_orders` | `customer_lifetime_value`  |
| Order    | `order_id`    | `raw_orders`    | `clean_orders` | `daily_revenue` (aggregated by date) |
| Product  | `product_id`  | `raw_products`  | `clean_orders` | `product_performance`      |

An entity is "Found" at a layer if at least one matching row exists. If it exists in an earlier layer but not a later one, it was dropped ("Stuck") by a transformation between them.

### Audit timestamps per layer

Used to report when an entity was last seen at each layer:
- Bronze: `ingested_at`
- Silver (`clean_orders`): `processed_at`
- Gold: `aggregated_at`

---

## AI Agent

The AI agent reads this document to understand the system. It gets all table and column metadata — names, types, keys, relationships — and the drop conditions between layers (from the before/after column notes) from here, not by running `SHOW TABLES` or `DESCRIBE TABLE`, and runs `SELECT` queries only to read actual data.

Using the architecture and data flow above, the agent works out which tables to query, in what order, and when to stop — for example, it does not look downstream for an entity that is already absent from its Bronze source, because later layers are derived from it. It returns a structured JSON answer (status, summary, per-layer trace, root cause, executed queries).
