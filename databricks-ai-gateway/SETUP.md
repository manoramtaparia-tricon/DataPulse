# Project Setup Guide

## Prerequisites

- Python 3.10 or higher
- A Databricks workspace (free tier works) with a running SQL Warehouse
- A Google Gemini API key

---

## Project Structure

```
databricks-gemini-mcp/
├── .env                       # Credentials (Databricks + Gemini)
├── .gitignore
├── requirements.txt
├── README.md                  # Architecture documentation (AI reads this)
├── SETUP.md                   # This file
├── DEMO_SCRIPT.md             # Presentation walkthrough
├── scripts/
│   ├── generate_data.py       # Step 1: Generate synthetic data → Bronze tables
│   └── build_pipeline.py      # Step 2: Build Silver and Gold from Bronze
└── src/
    ├── __init__.py
    ├── db_connection.py        # Shared Databricks connection module
    └── agent.py                # AI investigation agent (Gemini-powered)
```

---

## Step 1: Clone and Set Up Virtual Environment

```bash
cd /path/to/databricks-gemini-mcp

python3 -m venv venv
source venv/bin/activate
```

---

## Step 2: Install Dependencies

```bash
pip install --upgrade pip setuptools
pip install -r requirements.txt
```

This installs:
- `databricks-sql-connector` — connects to Databricks SQL Warehouse from Python
- `python-dotenv` — loads credentials from `.env` file
- `google-genai` — Google Gemini AI SDK

---

## Step 3: Configure Credentials

Edit the `.env` file with your values:

```
GEMINI_API_KEY="your-gemini-api-key"

DATABRICKS_HOST="your-workspace.cloud.databricks.com"
DATABRICKS_TOKEN="your-personal-access-token"
DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/your-warehouse-id"
DATABRICKS_CATALOG="test_catalog"
DATABRICKS_SCHEMA="default"
```

### Where to find these values:

**Gemini API Key:**
- Go to https://aistudio.google.com/apikey
- Create a new API key

**Databricks Host:**
- Your workspace URL without `https://` and without any query parameters
- Example: `dbc-8e5b636b-b0af.cloud.databricks.com`

**Databricks Token:**
- Databricks workspace → Profile icon (top-right) → User Settings → Developer → Access Tokens → Generate New Token

**Databricks HTTP Path:**
- Databricks workspace → SQL Warehouses → Click your warehouse → Connection Details → HTTP Path
- Example: `/sql/1.0/warehouses/2a7d5c7be5793e62`

---

## Step 4: Verify Databricks Connection

Make sure your SQL Warehouse is **Running** in the Databricks UI, then:

```bash
source venv/bin/activate

python -c "
from dotenv import load_dotenv; load_dotenv()
from src.db_connection import run_query
cols, rows = run_query('SELECT 1 AS test')
print('Connection successful:', rows[0][0])
"
```

You should see: `Connection successful: 1`

If it hangs or fails:
- Verify the warehouse is running (it auto-stops after inactivity)
- Check that your token hasn't expired
- Ensure the hostname doesn't include `https://` or `?o=...`

---

## Step 5: Load Data into Bronze Tables

This generates ~5,100 orders, 200 customers, and 50 products, then inserts them into Databricks.

```bash
python scripts/generate_data.py
```

Takes 3-5 minutes (inserts in batches of 100). You'll see progress like:

```
=== BRONZE: raw_products ===
  Inserted 50 products

=== BRONZE: raw_customers ===
  200/200 rows inserted

=== BRONZE: raw_orders ===
  5100/5100 rows inserted
```

---

## Step 6: Build Silver and Gold Tables

This reads the Bronze tables, cleans/joins/validates the data into Silver, then aggregates into Gold.

```bash
python scripts/build_pipeline.py
```

You'll see output like:

```
=== SILVER LAYER ===
  clean_orders: ~4500 rows

=== GOLD LAYER ===
  daily_revenue: ~365 rows
  customer_lifetime_value: ~190 rows
  product_performance: ~48 rows

Bronze → Silver drop-off: ~12% filtered
```

---

## Step 7: Run the AI Agent

```bash
python src/agent.py
```

The agent loads the README, pipeline code, and table schemas at startup, then presents an interactive prompt.

### Example questions to try:

```
What is the total revenue for March 2024?
```

```
Who are the top 5 customers by lifetime value?
```

```
Why might some orders be missing from the daily revenue report?
```

```
Which product category generates the most revenue?
```

```
Where does the daily_revenue metric come from?
```

```
Are there any orders in Bronze that reference products not in the product catalog?
```

Type `quit` to exit.

---

## Tables Reference

| Layer  | Table                    | Description                        | Approx Rows |
|--------|--------------------------|------------------------------------|-------------|
| Bronze | `raw_orders`             | Raw order transactions             | ~5,100      |
| Bronze | `raw_customers`          | Customer records                   | 200         |
| Bronze | `raw_products`           | Product catalog                    | 50          |
| Silver | `clean_orders`           | Cleaned, joined, enriched orders   | ~4,500      |
| Gold   | `daily_revenue`          | Revenue metrics by day             | ~365        |
| Gold   | `customer_lifetime_value`| Customer spend and behavior        | ~190        |
| Gold   | `product_performance`    | Product sales metrics              | ~48         |

All tables are in `test_catalog.default`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection hangs | Start the SQL Warehouse in Databricks UI and wait 1-2 min |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Run: `pip install certifi` then retry |
| `pip install` fails on pyarrow | Run: `pip install --upgrade pip setuptools` first |
| Gemini model not found error | Check model name in `src/agent.py` — currently `gemini-3.5-flash-lite` |
| Agent returns wrong SQL | Rephrase the question to be more specific |
| `generate_data.py` is slow | Normal — it inserts ~5,100 rows over the network in batches |
