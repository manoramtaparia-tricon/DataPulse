# E-Commerce Data Platform — Databricks Medallion Architecture

## Project Overview

This project builds an end-to-end data engineering platform for an e-commerce business using Databricks. It processes raw transactional data through a **Medallion Architecture** (Bronze → Silver → Gold) to produce business-ready analytics.

An **AI agent** powered by Google Gemini understands the system by reading this documentation and the pipeline code. It can answer natural language questions about the data by querying the Databricks tables directly.

### Business Problem

The e-commerce business needs a unified data platform that:
- Ingests raw data from multiple source systems (web app, mobile app, POS terminals, partner APIs)
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
    subgraph Sources
        S1[Web App]
        S2[Mobile App]
        S3[POS Terminal]
        S4[Partner API]
    end

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

    subgraph AI Agent
        AG[Gemini Agent]
    end

    S1 & S2 & S3 & S4 --> B1 & B2 & B3
    B1 & B2 & B3 --> SV
    SV --> G1 & G2 & G3
    AG -.->|queries| B1 & B2 & B3
    AG -.->|queries| SV
    AG -.->|queries| G1 & G2 & G3
```

---

## Data Flow

```mermaid
flowchart TD
    subgraph Bronze["Bronze — Raw Ingestion"]
        RO[raw_orders<br/>Orders as received from source systems]
        RC[raw_customers<br/>Customer records from source systems]
        RP[raw_products<br/>Product catalog from source systems]
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

- **`test_catalog.default.clean_orders`** — Enriched order data combining orders, customers, and products. Pipeline: `scripts/build_pipeline.py`

### Gold Layer

Business-ready aggregated metrics derived from the Silver layer.

- **`test_catalog.default.daily_revenue`** — Revenue and order metrics aggregated by day
- **`test_catalog.default.customer_lifetime_value`** — Customer spend, tenure, and behavior metrics
- **`test_catalog.default.product_performance`** — Product sales, revenue, and reach metrics

Pipeline for all Gold tables: `scripts/build_pipeline.py`

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

To trace any Gold metric back to its source, follow the lineage through `clean_orders` back to the Bronze tables. The transformation logic is defined in `scripts/build_pipeline.py`.

---

## Project Structure

```
├── scripts/
│   ├── generate_data.py      # Generates synthetic data and loads Bronze tables
│   └── build_pipeline.py     # Builds Silver and Gold tables from Bronze
├── src/
│   ├── db_connection.py       # Databricks connection module
│   └── agent.py               # AI investigation agent
├── .env                       # Credentials (not committed)
└── README.md                  # This file
```

---

## AI Agent

The AI agent reads this documentation and the pipeline code (`scripts/build_pipeline.py`) to understand the system. When asked a question, it:

1. Determines which tables are relevant
2. Generates SQL queries to investigate
3. Executes queries against Databricks
4. If needed, generates follow-up queries for deeper investigation
5. Explains the results using its understanding of the architecture and pipeline logic

The agent restricts itself to SELECT queries only.
