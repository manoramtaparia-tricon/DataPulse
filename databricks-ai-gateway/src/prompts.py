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
  {steps_so_far}      - layers already checked this trace, with results (lineage step)
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


LINEAGE_STEP = """You trace a single entity through the Medallion layers (Bronze -> Silver -> Gold), ONE layer at a time. You decide the next step; a separate program runs the SQL you return and calls you again with the result.

PROJECT DOCUMENTATION (see "Entity Lineage & Tracking" for the table, key column and audit timestamp per layer, and follow the "Lineage tracing procedure" there — it defines the order to check layers in and exactly when to stop):
{readme}

ENTITY TYPE: {entity_type}
ENTITY VALUE: {entity_value}
(ids in this platform are integers — do NOT quote them; only quote when matching a text column such as a name)

LAYERS ALREADY CHECKED THIS TRACE (in order):
{steps_so_far}

Following the lineage tracing procedure in the documentation, decide the SINGLE next action:
- If a next layer should still be checked, return its presence-check query.
- If the entity was not found (count = 0) in the most recent layer checked, or the final (Gold) layer has already been checked, stop.

Return ONLY one JSON object (no prose, no code fence).
To check the next layer:
{{"action": "query",
  "stage": "Bronze" | "Silver" | "Gold",
  "layer": "Bronze" | "Silver" | "Gold",
  "table": "<fully-qualified table name>",
  "detail": "<short description of what this table holds>",
  "sql": "SELECT COUNT(*) AS n, MAX(<audit timestamp column>) AS last_seen FROM <table> WHERE <key column> = {entity_value}"}}
To stop:
{{"action": "stop", "reason": "<why you are stopping>"}}

Use the correct key column (customer_id / order_id / product_id, or a name column if the value is a name) and the correct audit column (ingested_at for Bronze, processed_at for Silver, aggregated_at for Gold). SELECT only."""


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
