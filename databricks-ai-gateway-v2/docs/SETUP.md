# Project Setup Guide

## Prerequisites

- Python 3.10 or higher
- A Databricks workspace (free tier works) with a running SQL Warehouse
- A Google Gemini API key

---

## Project Structure

```
databricks-ai-gateway/
├── .env                        # Credentials (Databricks + Gemini)
├── .gitignore
├── requirements.txt
├── AGENT_CONTEXT.md            # Project knowledge the agent reads (schema, flow, keys)
├── docs/
│   ├── AGENT_FLOW.md           # How ai_agent.py + ui_api.py work end to end
│   ├── MODEL_INFO.md           # Gemini model reference
│   └── SETUP.md                # This file
├── scripts/
│   ├── initial_load/           # One-time: build the first full dataset
│   │   ├── generate_data.py    #   Step 1: synthetic data → Bronze tables
│   │   └── build_pipeline.py   #   Step 2: Bronze → Silver → Gold
│   └── additional_data/        # Extra data generated later via the Databricks UI
│       ├── generate_data.py
│       └── build_pipeline.py
├── notebooks/                  # Databricks import-ready jobs (one per layer)
└── src/
    ├── __init__.py
    ├── db_connection.py         # Shared Databricks connection module
    ├── ai_agent.py              # Generic investigation agent (DataAgent)
    ├── ui_api.py                # FastAPI layer the UI calls (port 3001)
    └── prompts/                 # Agent instruction templates
        ├── __init__.py
        └── templates.py         # SYSTEM_INSTRUCTION + SYNTHESIS_INSTRUCTION
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
- `fastapi` and `uvicorn` - serve the HTTP API
- `nemoguardrails` - enforce input and output safety checks on API requests

---

## Step 3: Configure Credentials

Edit the `.env` file with your values:

```
GEMINI_API_KEY="your-gemini-api-key"
GUARDRAILS_MODEL="gemini-3.5-flash-lite"

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
python scripts/initial_load/generate_data.py
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
python scripts/initial_load/build_pipeline.py
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

The agent loads `AGENT_CONTEXT.md` and the pipeline code at startup, then works out
which tables to query from that documentation. There are two ways to run it.

**A) Command line (quick testing):**

```bash
python -m src.ai_agent "Track whether customer 42 is present in all layers"
```

Omit the question for an interactive prompt (type `quit` to exit):

```bash
python -m src.ai_agent
```

**B) API server (what the frontend calls):**

```bash
uvicorn src.ui_api:app --port 3001 --reload
```

This serves `POST /api/diagnose` on port **3001** — the port the Angular UI's
`project-chat.service.ts` is configured to call. See `AGENT_FLOW.md` for the full
request-to-response flow.

The API checks questions before investigation and checks both the agent result
and UI response before returning them. Policy blocks return HTTP 403 with code
`GUARDRAIL_BLOCKED` and an `input` or `output` stage. Failed safety checks return
HTTP 503 with code `GUARDRAIL_UNAVAILABLE`; unchecked responses are never returned.
`GUARDRAILS_MODEL` is optional and defaults to `gemini-3.5-flash-lite`, using the
agent's Gemini client and API key. Direct command-line agent calls are not
guarded. See [the guardrails guide](../guardrails/README.md) for policy details
and offline regression tests.

> Docs are loaded at **startup**, and `--reload` only watches `.py` files — restart
> the server after editing `AGENT_CONTEXT.md` for changes to take effect.

### Example questions to try:

```
Track whether customer 42 is present in all layers
```

```
Why is customer 421 missing from the Gold table?
```

```
Where did order 1234 get stuck in the pipeline?
```

```
Are there any orders in Bronze that reference products not in the product catalog?
```

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
| Gemini model not found error | Check `MODEL` in `src/ai_agent.py` (or the `GEMINI_MODEL` env var) — currently `gemini-3.5-flash-lite` |
| `Address already in use` on port 3001 | A server is already running — stop it with `pkill -f "ui_api:app"` before restarting |
| Agent returns wrong SQL | Rephrase the question to be more specific |
| `generate_data.py` is slow | Normal — it inserts ~5,100 rows over the network in batches |
