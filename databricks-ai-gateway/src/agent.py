"""AI agent that investigates data across Bronze/Silver/Gold layers using Gemini."""

import os
import sys
import re
import json
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

TONE_SUCCESS = "success"
TONE_WARNING = "warning"
TONE_MUTED = "muted"

STATUS_ICONS = {
    "Found": "✓",
    "Stuck": "■",
    "Not found": "✗",
    "Error": "!",
}


class Agent:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.project_root = os.path.join(os.path.dirname(__file__), "..")
        print("Loading project context...")
        self.readme = self._load_file("DATA_PLATFORM.md")
        self.pipeline_code = self._load_file("scripts/build_pipeline.py")
        print("Context loaded.\n")

    def _load_file(self, relative_path):
        path = os.path.join(self.project_root, relative_path)
        with open(path) as f:
            return f.read()

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

    def _extract_json(self, text):
        """Pull the first JSON object/array out of a model response."""
        if not text:
            return None
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        candidate = (fenced.group(1) if fenced else text).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass
        starts = [i for i in (candidate.find("{"), candidate.find("[")) if i != -1]
        if not starts:
            return None
        start = min(starts)
        end = max(candidate.rfind("}"), candidate.rfind("]"))
        if end <= start:
            return None
        try:
            return json.loads(candidate[start:end + 1])
        except Exception:
            return None

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
        classification = self._classify(question) or {}
        if classification.get("mode") == "lineage" and classification.get("entity_value") not in (None, ""):
            return self._investigate_lineage(question, classification)
        return self._investigate_general(question)

    def _classify(self, question):
        prompt = f"""You route questions about an e-commerce Databricks platform (Medallion: Bronze -> Silver -> Gold).

PROJECT DOCUMENTATION (includes the full Table & Column Reference — all tables, columns, types and keys):
{self.readme}

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
        return self._extract_json(self._call_gemini(prompt))

    def _investigate_lineage(self, question, info):
        entity_type = info.get("entity_type")
        entity_value = info.get("entity_value")
        entity_label = info.get("entity_label") or f"{entity_type or 'entity'} {entity_value}"

        print(f"  Tracing {entity_label} across layers...")
        stages = self._plan_lineage(entity_type, entity_value)
        if not stages:
            print("  Could not plan a lineage trace — falling back to general analysis.\n")
            return self._investigate_general(question)

        executed = []
        for stage in stages:
            sql = stage["sql"]
            print(f"  Checking {stage.get('stage')} ({stage.get('table')})...")
            columns, rows, status = self._run_sql(sql)
            count, last_seen = None, None
            if rows:
                try:
                    count = int(rows[0][0])
                except (ValueError, TypeError, IndexError):
                    count = None
                if len(rows[0]) > 1 and rows[0][1] is not None:
                    last_seen = str(rows[0][1])
            stage["count"] = count
            stage["last_seen"] = last_seen
            stage["error"] = None if count is not None else status
            executed.append(
                f"--- {stage.get('stage')} ({stage.get('table')}) ---\n"
                f"SQL: {sql}\nRESULT: count={count}, last_seen={last_seen} {status}"
            )

        timeline, overall = self._build_timeline(stages)
        message = self._explain_lineage(question, entity_label, timeline, overall)

        slug = self._slugify(entity_label)
        obj = {
            "title": f"{entity_label} — Lineage Trace",
            "entityType": entity_type,
            "entityId": entity_value,
            "timeline": timeline,
            "summary": {"status": overall, "message": message},
            "actions": [
                {"label": "Run RCA Analysis", "tone": "primary"},
                {"label": "View Executed Queries", "tone": "secondary"},
            ],
        }
        data = {slug: obj}

        self._render_timeline(obj)
        detail = f"\n--- QUERIES EXECUTED ---\n\n" + "\n\n".join(executed)
        return {"mode": "lineage", "data": data, "text": message, "detail": detail}

    def _plan_lineage(self, entity_type, entity_value):
        prompt = f"""You build a lineage trace plan for a single entity across the Medallion layers.

PROJECT DOCUMENTATION (see the "Table & Column Reference", "Entity Lineage & Tracking" and "Join Keys" sections for table names, columns, data types, keys and audit timestamp columns):
{self.readme}

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
        plan = self._extract_json(self._call_gemini(prompt))
        if not isinstance(plan, list):
            return []
        stages = []
        for item in plan:
            if not isinstance(item, dict):
                continue
            sql = (item.get("sql") or "").strip().rstrip(";")
            valid, _ = self._validate_sql(sql)
            if sql and valid:
                item["sql"] = sql
                stages.append(item)
        return stages

    def _build_timeline(self, stages):
        # A stage is "Stuck" when it is the first absent layer after the entity was
        # present earlier; any later absent layers are "Not found".
        timeline = []
        seen_present = False
        stuck_marked = False
        for stage in stages:
            count = stage.get("count")
            if count is None and stage.get("error"):
                status, tone = "Error", TONE_WARNING
            elif count and count > 0:
                status, tone = "Found", TONE_SUCCESS
                seen_present = True
            elif seen_present and not stuck_marked:
                status, tone = "Stuck", TONE_WARNING
                stuck_marked = True
            else:
                status, tone = "Not found", TONE_MUTED
            timeline.append({
                "stage": stage.get("stage"),
                "layer": stage.get("layer"),
                "table": stage.get("table"),
                "detail": stage.get("detail"),
                "count": count,
                "status": status,
                "timestamp": stage.get("last_seen") or "--",
                "tone": tone,
            })

        statuses = [t["status"] for t in timeline]
        if statuses and all(s == "Found" for s in statuses):
            overall = "COMPLETE"
        elif "Found" not in statuses:
            overall = "MISSING"
        elif "Stuck" in statuses:
            overall = "STUCK"
        else:
            overall = "PARTIAL"
        return timeline, overall

    def _explain_lineage(self, question, entity_label, timeline, overall):
        trace = "\n".join(
            f"- {t['stage']} ({t['table']}): {t['status']} (count={t['count']})"
            for t in timeline
        )
        prompt = f"""You explain data lineage results to a business user.

PROJECT DOCUMENTATION:
{self.readme}

PIPELINE CODE (the exact transformations that move data Bronze -> Silver -> Gold):
{self.pipeline_code}

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
        return self._call_gemini(prompt).strip()

    def _slugify(self, label):
        slug = re.sub(r"[^a-z0-9]+", "-", str(label).lower()).strip("-")
        return slug or "entity"

    def _render_timeline(self, obj):
        print(f"\n{'=' * 60}")
        print(f"  {obj['title']}")
        print(f"{'=' * 60}\n")
        for t in obj["timeline"]:
            icon = STATUS_ICONS.get(t["status"], "-")
            line = f"  {icon}  {str(t['stage']):<8} {t['status']:<10} {t.get('table', '')}"
            if t.get("count") is not None:
                line += f"  ({t['count']} rows)"
            print(line)
        print(f"\n  STATUS: {obj['summary']['status']}")
        print(f"  {obj['summary']['message']}")
        print(f"\n{'=' * 60}")

    def _investigate_general(self, question):
        all_query_results = []

        # Round 1: Generate initial investigation queries
        plan_prompt = f"""You are a data engineer investigating a question about an e-commerce data platform built on Databricks using the Medallion Architecture.

PROJECT DOCUMENTATION (includes the full Table & Column Reference — all tables, columns, data types and keys):
{self.readme}

PIPELINE CODE (this is the actual code that builds Silver and Gold tables — use it to understand the exact transformations):
{self.pipeline_code}

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
            text = f"Could not generate queries.\n\nGemini response:\n{plan_text}"
            print(text)
            return {"mode": "general", "data": None, "text": text, "detail": ""}

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

Keep your answer focused and practical. Use the documentation to explain the architecture but rely on the actual query results for the data.

Write in plain text only — no Markdown. Do not use asterisks for bold, hash symbols for headings, or backticks. Use short paragraphs and, where you list items, plain numbered lines (e.g. "1. ...")."""

        print("  Analyzing results...\n")
        analysis = self._call_gemini(analysis_prompt)

        print(f"\n{'=' * 60}")
        print("  ANSWER")
        print(f"{'=' * 60}\n")
        print(analysis)
        print(f"\n{'=' * 60}")

        detail = f"\n--- QUERIES EXECUTED ---\n\n{all_results_text}"
        data = {"question": question, "answer": analysis}
        return {"mode": "general", "data": data, "text": analysis, "detail": detail}


def main():
    print("=" * 60)
    print("  E-Commerce Data Platform — AI Investigation Agent")
    print("  Medallion Architecture: Bronze → Silver → Gold")
    print("=" * 60)
    print()

    agent = Agent()

    print("Ask questions about the data (type 'quit' to exit)")
    print("Examples:")
    print('  Lineage:  "Is customer 42 present in all layers?"')
    print('  Lineage:  "Where did order 1234 get stuck?"')
    print('  General:  "What is the total revenue for January 2024?"')
    print('  General:  "Who are the top 5 customers by lifetime value?"')
    print('  General:  "Where does the daily_revenue metric come from?"')
    print()

    while True:
        question = input("Question: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        print(f"\nInvestigating...\n")
        result = agent.investigate(question)

        if result["mode"] == "lineage":
            if input("\nShow structured JSON? (y/n): ").strip().lower() == "y":
                print(json.dumps(result["data"], indent=2, default=str, ensure_ascii=False))
            if input("Show executed queries? (y/n): ").strip().lower() == "y":
                print(result["detail"])
        else:
            if input("\nShow response as JSON? (y/n): ").strip().lower() == "y":
                print(json.dumps(result["data"], indent=2, default=str, ensure_ascii=False))
            if input("Show query details? (y/n): ").strip().lower() == "y":
                print(result["detail"])


if __name__ == "__main__":
    main()
