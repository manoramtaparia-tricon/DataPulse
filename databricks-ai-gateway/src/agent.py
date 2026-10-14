"""AI agent that investigates data across Bronze/Silver/Gold layers using Gemini."""

import os
import sys
import re
import warnings

warnings.filterwarnings("ignore", message=".*automatic function calling.*")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from google import genai
from src.db_connection import run_query

SCHEMA = "test_catalog.default"
MAX_RESULT_ROWS = 50
MAX_QUERY_ROUNDS = 3

TABLES = [
    f"{SCHEMA}.raw_orders",
    f"{SCHEMA}.raw_customers",
    f"{SCHEMA}.raw_products",
    f"{SCHEMA}.clean_orders",
    f"{SCHEMA}.daily_revenue",
    f"{SCHEMA}.customer_lifetime_value",
    f"{SCHEMA}.product_performance",
]
# remove

class Agent:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.project_root = os.path.join(os.path.dirname(__file__), "..")
        print("Loading project context...")
        self.readme = self._load_file("README.md")
        self.pipeline_code = self._load_file("scripts/build_pipeline.py")
        self.schemas = {}
        print("Loading table schemas from Databricks...")
        for table in TABLES:
            self.schemas[table] = self._fetch_schema(table)
        print(f"Loaded schemas for {len(self.schemas)} tables.\n")

    def _load_file(self, relative_path):
        path = os.path.join(self.project_root, relative_path)
        with open(path) as f:
            return f.read()

    def _fetch_schema(self, table):
        try:
            columns, rows = run_query(f"DESCRIBE TABLE {table}")
            lines = []
            for row in rows:
                col_name, col_type = str(row[0]).strip(), str(row[1]).strip()
                if col_name.startswith("#") or col_name == "":
                    continue
                lines.append(f"  {col_name} ({col_type})")
            return "\n".join(lines)
        except Exception as e:
            return f"  (error fetching schema: {e})"

    def _build_schema_context(self):
        parts = []
        for table, schema in self.schemas.items():
            parts.append(f"Table: {table}\n{schema}")
        return "\n\n".join(parts)

    def _extract_sql(self, text):
        queries = re.findall(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if not queries:
            queries = re.findall(r"```\s*(SELECT.*?)```", text, re.DOTALL | re.IGNORECASE)
        result = []
        for q in queries:
            q = q.strip().rstrip(";")
            if q:
                result.append(q)
        return result

    def _validate_sql(self, query):
        lines = [l.strip() for l in query.strip().splitlines() if l.strip() and not l.strip().startswith("--")]
        if not lines:
            return False, "Empty query."
        normalized = "\n".join(lines).upper()
        if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
            return False, "Only SELECT queries are allowed."
        dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "MERGE"]
        for kw in dangerous:
            if re.search(rf'\b{kw}\b', normalized):
                return False, f"Query contains forbidden keyword: {kw}"
        return True, ""

    def _run_sql(self, query):
        valid, reason = self._validate_sql(query)
        if not valid:
            return None, None, reason
        try:
            columns, rows = run_query(query)
            if len(rows) > MAX_RESULT_ROWS:
                rows = rows[:MAX_RESULT_ROWS]
                truncated = True
            else:
                truncated = False
            return columns, rows, f"({len(rows)} rows{'— truncated' if truncated else ''})"
        except Exception as e:
            return None, None, f"ERROR: {e}"

    def _format_results(self, columns, rows):
        if not columns or not rows:
            return "(no results)"
        header = " | ".join(f"{col:>20}" for col in columns)
        lines = [header, "-" * len(header)]
        for row in rows:
            lines.append(" | ".join(f"{str(v):>20}" for v in row))
        return "\n".join(lines)

    def _call_gemini(self, prompt):
        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        return response.text

    def investigate(self, question):
        schema_context = self._build_schema_context()
        all_query_results = []

        # Round 1: Generate initial investigation queries
        plan_prompt = f"""You are a data engineer investigating a question about an e-commerce data platform built on Databricks using the Medallion Architecture.

PROJECT DOCUMENTATION:
{self.readme}

PIPELINE CODE (this is the actual code that builds Silver and Gold tables — use it to understand the exact transformations):
{self.pipeline_code}

LIVE TABLE SCHEMAS:
{schema_context}

USER QUESTION: "{question}"

Generate 2-4 SQL queries (Spark SQL syntax, SELECT only) to answer this question.
Think about which layer (Bronze, Silver, Gold) has the relevant data.
If the question is about a metric, trace it back through the layers.
Add a one-line comment at the top of each query explaining what it checks.

Return ONLY the SQL queries, each in a separate ```sql``` code block."""

        print("  Generating investigation queries...")
        plan_text = self._call_gemini(plan_prompt)
        queries = self._extract_sql(plan_text)

        if not queries:
            return f"Could not generate queries.\n\nGemini response:\n{plan_text}"

        # Execute queries
        for i, query in enumerate(queries, 1):
            print(f"  Running query {i}/{len(queries)}...")
            columns, rows, status = self._run_sql(query)
            result_text = self._format_results(columns, rows) if columns else status
            all_query_results.append(f"--- Query {i} ---\nSQL: {query}\n\n{result_text}\n{status}")

        # Check if we need follow-up queries (multi-step reasoning)
        for round_num in range(2, MAX_QUERY_ROUNDS + 1):
            results_so_far = "\n\n".join(all_query_results)
            followup_prompt = f"""You are investigating this question: "{question}"

Results so far:
{results_so_far}

Do you need any follow-up queries to fully answer the question?
If YES, generate 1-2 additional SQL queries in ```sql``` code blocks.
If NO, respond with exactly: NO_FOLLOWUP_NEEDED"""

            followup_text = self._call_gemini(followup_prompt)
            if "NO_FOLLOWUP_NEEDED" in followup_text:
                break

            followup_queries = self._extract_sql(followup_text)
            if not followup_queries:
                break

            print(f"  Running {len(followup_queries)} follow-up queries (round {round_num})...")
            for j, query in enumerate(followup_queries, 1):
                idx = len(all_query_results) + 1
                columns, rows, status = self._run_sql(query)
                result_text = self._format_results(columns, rows) if columns else status
                all_query_results.append(f"--- Query {idx} ---\nSQL: {query}\n\n{result_text}\n{status}")

        # Final analysis
        all_results_text = "\n\n".join(all_query_results)
        analysis_prompt = f"""You are a data engineer explaining query results to a business user.

PROJECT DOCUMENTATION:
{self.readme}

PIPELINE CODE (actual transformation logic):
{self.pipeline_code}

USER QUESTION: "{question}"

INVESTIGATION RESULTS:
{all_results_text}

Based on the actual query results:
1. Answer the user's question clearly and concisely
2. Reference specific data from the results (numbers, names, dates)
3. If the question involves tracing data lineage, explain which tables and transformations are involved
4. If data is missing, explain which transformation step likely filtered it out and why

Keep your answer focused and practical. Use the documentation to explain the architecture but rely on the actual query results for the data."""

        print("  Analyzing results...\n")
        analysis = self._call_gemini(analysis_prompt)

        print(f"\n{'=' * 60}")
        print("  ANSWER")
        print(f"{'=' * 60}\n")
        print(analysis)
        print(f"\n{'=' * 60}")

        detail = f"\n--- QUERIES EXECUTED ---\n\n{all_results_text}"
        return detail


def main():
    print("=" * 60)
    print("  E-Commerce Data Platform — AI Investigation Agent")
    print("  Medallion Architecture: Bronze → Silver → Gold")
    print("=" * 60)
    print()

    agent = Agent()

    print("Ask questions about the data (type 'quit' to exit)")
    print("Examples:")
    print('  - "What is the total revenue for January 2024?"')
    print('  - "Who are the top 5 customers by lifetime value?"')
    print('  - "Why might some orders be missing from the daily revenue report?"')
    print('  - "Which products have the highest return rate?"')
    print('  - "Where does the daily_revenue metric come from?"')
    print()

    while True:
        question = input("Question: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        print(f"\nInvestigating...\n")
        detail = agent.investigate(question)
        show = input("\nShow query details? (y/n): ").strip().lower()
        if show == "y":
            print(detail)


if __name__ == "__main__":
    main()
