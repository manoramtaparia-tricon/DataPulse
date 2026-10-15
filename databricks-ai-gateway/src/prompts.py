"""Prompt templates for the investigation agent.

Each template is a plain string with ``{placeholder}`` fields filled via
``str.format(...)``. Keeping the wording here (separate from agent.py logic)
means prompts can be read and tuned in one place without touching code.

Placeholders used:
  {readme}            - DATA_PLATFORM.md contents (tables, columns, keys, lineage)
  {pipeline_code}     - build_pipeline.py source (exact transformations)
  {question}          - the user's question
  {entity_type}       - customer | order | product (lineage)
  {entity_value}      - the entity id/name (lineage)
  {entity_label}      - human label, e.g. "Customer 42" (lineage)
  {overall}           - overall lineage status (COMPLETE/STUCK/MISSING/PARTIAL)
  {trace}             - layer-by-layer trace lines (lineage)
  {results_so_far}    - executed query results so far (general follow-up)
  {all_results_text}  - all executed query results (general analysis)
"""

CLASSIFY = """You route questions about an e-commerce Databricks platform (Medallion: Bronze -> Silver -> Gold).

PROJECT DOCUMENTATION (includes the full Table & Column Reference — all tables, columns, types and keys):
{readme}

QUESTION: "{question}"

Decide the mode:
- "lineage": the user wants to know whether ONE specific entity (a particular customer, order, or product, named by an id or name) exists in / flows through the layers.
  Examples: "is customer 42 in all layers", "where did order 1234 get stuck", "track product 7", "is customer C123 present in bronze silver and gold".
- "general": any other analytics question (totals, top-N, trends, why a metric looks a certain way, etc.).

If lineage, identify the entity.

Return ONLY a JSON object (no prose, no code fence):
{{"mode": "lineage" | "general",
  "entity_type": "customer" | "order" | "product" | null,
  "entity_value": "<the id/name exactly as the user gave it, or null>",
  "entity_label": "<short human label, e.g. 'Customer 42', or null>"}}"""


PLAN_LINEAGE = """You build a lineage trace plan for a single entity across the Medallion layers.

PROJECT DOCUMENTATION (see the "Table & Column Reference", "Entity Lineage & Tracking" and "Join Keys" sections for table names, columns, data types, keys and audit timestamp columns):
{readme}

ENTITY TYPE: {entity_type}
ENTITY VALUE: {entity_value}
(ids in this platform are integers — do NOT quote them; only quote when matching a text column such as a name)

List the tables this entity passes through, ordered Bronze -> Silver -> Gold, skipping any table that does not contain this entity. For each, produce a presence check.

Return ONLY a JSON array (no prose, no code fence); each element:
{{"stage": "Bronze" | "Silver" | "Gold",
  "layer": "Bronze" | "Silver" | "Gold",
  "table": "<fully-qualified table name>",
  "detail": "<short description of what this table holds>",
  "sql": "SELECT COUNT(*) AS n, MAX(<audit timestamp column>) AS last_seen FROM <table> WHERE <key column> = {entity_value}"}}

Use the correct key column (customer_id / order_id / product_id, or a name column if the value is a name) and the correct audit column from the documentation above (ingested_at for Bronze, processed_at for Silver, aggregated_at for Gold). SELECT only."""


EXPLAIN_LINEAGE = """You explain data lineage results to a business user.

PROJECT DOCUMENTATION:
{readme}

PIPELINE CODE (the exact transformations that move data Bronze -> Silver -> Gold):
{pipeline_code}

QUESTION: "{question}"
ENTITY: {entity_label}
OVERALL STATUS: {overall}

LAYER-BY-LAYER TRACE:
{trace}

Write 1-3 sentences for a business user:
- COMPLETE: confirm the entity reached every layer.
- STUCK / PARTIAL: name the exact transformation step or filter in the pipeline code that most likely dropped it (e.g. the INNER JOIN to customers/products, the quantity/region/date validation, the duplicate dedup, or the cancelled/returned filter) and why.
- MISSING: say it was never found in any layer.
Be specific and concise. Plain text only, no markdown."""


GENERAL_PLAN = """You are a data engineer investigating a question about an e-commerce data platform built on Databricks using the Medallion Architecture.

PROJECT DOCUMENTATION (includes the full Table & Column Reference — all tables, columns, data types and keys):
{readme}

PIPELINE CODE (this is the actual code that builds Silver and Gold tables — use it to understand the exact transformations):
{pipeline_code}

USER QUESTION: "{question}"

Generate 2-4 SQL queries (Spark SQL syntax, SELECT only) to answer this question.
Think about which layer (Bronze, Silver, Gold) has the relevant data.
If the question is about a metric, trace it back through the layers.
Add a one-line comment at the top of each query explaining what it checks.

Return ONLY the SQL queries, each in a separate ```sql``` code block."""


GENERAL_FOLLOWUP = """You are investigating this question: "{question}"

Results so far:
{results_so_far}

Do you need any follow-up queries to fully answer the question?
If YES, generate 1-2 additional SQL queries in ```sql``` code blocks.
If NO, respond with exactly: NO_FOLLOWUP_NEEDED"""


GENERAL_ANALYSIS = """You are a data engineer explaining query results to a business user.

PROJECT DOCUMENTATION:
{readme}

PIPELINE CODE (actual transformation logic):
{pipeline_code}

USER QUESTION: "{question}"

INVESTIGATION RESULTS:
{all_results_text}

Based on the actual query results:
1. Answer the user's question clearly and concisely
2. Reference specific data from the results (numbers, names, dates)
3. If the question involves tracing data lineage, explain which tables and transformations are involved
4. If data is missing, explain which transformation step likely filtered it out and why

Keep your answer focused and practical. Use the documentation to explain the architecture but rely on the actual query results for the data.

Write in plain text only — no Markdown. Do not use asterisks for bold, hash symbols for headings, or backticks. Use short paragraphs and, where you list items, plain numbered lines (e.g. "1. ...")."""
