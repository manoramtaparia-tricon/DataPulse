import os
import re
import sys
import json
import glob
import warnings

warnings.filterwarnings("ignore", message=".*automatic function calling.*")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

try:
    from src.db_connection import run_query
    from src.prompts import (
        SYSTEM_INSTRUCTION, SYNTHESIS_INSTRUCTION,
        RCA_SYSTEM_INSTRUCTION, RCA_SYNTHESIS_INSTRUCTION,
    )
except ImportError:  # allow running the file directly without the package
    from db_connection import run_query
    from prompts import (
        SYSTEM_INSTRUCTION, SYNTHESIS_INSTRUCTION,
        RCA_SYSTEM_INSTRUCTION, RCA_SYNTHESIS_INSTRUCTION,
    )


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_DOC_FILES = ["AGENT_CONTEXT.md"]
# RCA needs the tracking docs plus execution/evidence docs and the pipeline code itself.
DEFAULT_RCA_DOC_FILES = [
    "AGENT_CONTEXT.md",
    "RCA_CONTEXT.md",
    "databricks_notebooks/02_build_silver.py",
    "databricks_notebooks/03_build_gold.py",
]

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_RESULT_ROWS = 50          # cap rows returned to the model per query
MAX_SQL_CALLS = 12            # runaway guard: the model decides when to stop, this just caps it
MAX_RCA_SQL_CALLS = int(os.getenv("MAX_RCA_SQL_CALLS", "15"))  # RCA digs deeper (rules, freshness, runs)
MAX_CELL_CHARS = 1000         # long cells (e.g. DESCRIBE HISTORY maps) are truncated for the model

FORBIDDEN_SQL =["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "MERGE", "GRANT", "REVOKE"]

# RCA may also read a Delta table's commit history: exactly "DESCRIBE HISTORY <table> [LIMIT n]".
_DESCRIBE_HISTORY_RE = re.compile(
    r"^DESCRIBE\s+HISTORY\s+[`\w.]+(\s+LIMIT\s+\d+)?$", re.IGNORECASE
)

# Tracking statuses that must never lead to RCA (errors or guardrail/out-of-scope replies).
NON_RCA_STATUSES = {"ERROR", "BLOCKED", "OUT_OF_SCOPE", "REJECTED", "GUARDRAIL_BLOCKED"}


def rca_eligibility(result):
    """Decide deterministically, from the tracking trace, whether RCA applies.

    RCA is offered only when a specific entity was tracked and at least one layer that was
    checked did not contain it. If it was absent from the very first layer it is MISSING;
    if it was present earlier and absent later it is STUCK. Generic answers (no entity or
    no trace, e.g. a guardrail/out-of-scope reply), errors, and fully-found entities are
    not eligible. The model's free-form status word is not trusted for this decision.
    """
    result = result or {}
    entity = result.get("entity") or {}
    trace = result.get("trace") or []
    status = str(result.get("status") or "").upper()

    def no(reason):
        return {"eligible": False, "reason": reason}

    if result.get("guardrail") or status in NON_RCA_STATUSES:
        return no("Generic or blocked response; nothing to analyse.")
    if entity.get("id") in (None, ""):
        return no("No specific entity was tracked.")
    if not isinstance(trace, list) or not trace:
        return no("No per-layer trace was produced.")

    last_present = None
    for step in trace:
        if not isinstance(step, dict):
            continue
        if step.get("found"):
            last_present = step
            continue
        return {
            "eligible": True,
            "verdict": "STUCK" if last_present else "MISSING",
            "gap_layer": step.get("layer"),
            "gap_table": step.get("table"),
            "last_present_layer": (last_present or {}).get("layer"),
            "reason": (
                f"Found in {last_present.get('layer')} but not in {step.get('layer')}."
                if last_present else f"Not found in {step.get('layer')}."
            ),
        }
    return no("The entity was found in every layer that was checked.")


class DataAgent:
    def __init__(self, doc_files=None, rca_doc_files=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (check your .env).")
        self.client = genai.Client(api_key=api_key)
        self.documentation = self._load_documentation(doc_files, "DOC_FILES", DEFAULT_DOC_FILES)
        self.rca_documentation = self._load_documentation(
            rca_doc_files, "RCA_DOC_FILES", DEFAULT_RCA_DOC_FILES
        )
        self._tool = _sql_tool(
            "Run a single read-only SELECT query against the data platform and "
            "return up to %d rows. Use documented table and column names only." % MAX_RESULT_ROWS,
            "A single SELECT (or WITH ... SELECT) statement. No DDL/DML.",
        )
        self._rca_tool = _sql_tool(
            "Run a single read-only statement against the data platform and return up to "
            "%d rows: a SELECT (or WITH ... SELECT), or DESCRIBE HISTORY <table> [LIMIT n] "
            "to read a Delta table's commit history. Use documented names only." % MAX_RESULT_ROWS,
            "A single SELECT / WITH ... SELECT, or DESCRIBE HISTORY <table> [LIMIT n]. No DDL/DML.",
        )

    # ------------------------------------------------------------------ docs

    def _load_documentation(self, doc_files, env_var, default):
        if doc_files is None:
            env = os.getenv(env_var)
            doc_files = [p.strip() for p in env.split(",")] if env else default
        sections = []
        for rel in doc_files:
            for path in sorted(glob.glob(os.path.join(PROJECT_ROOT, rel))):
                try:
                    with open(path) as f:
                        text = f.read()
                except OSError:
                    continue
                # Strip HTML-commented (<!-- ... -->) parts so disabled doc sections aren't sent.
                text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
                name = os.path.relpath(path, PROJECT_ROOT)
                sections.append(f"\n----- FILE: {name} -----\n{text.strip()}\n")
        if not sections:
            raise RuntimeError(
                "No documentation loaded. Expected one of: %s" % ", ".join(doc_files)
            )
        return "\n".join(sections)

    # ------------------------------------------------------------------- SQL

    def _validate_sql(self, query, allow_history=False):
        stripped = (query or "").strip().rstrip(";").strip()
        if not stripped:
            return False, "Empty query."
        if ";" in stripped:
            return False, "Only a single statement is allowed."
        if allow_history and _DESCRIBE_HISTORY_RE.match(stripped):
            return True, stripped
        head = stripped.upper()
        if not (head.startswith("SELECT") or head.startswith("WITH")):
            return False, "Only SELECT queries are allowed."
        for kw in FORBIDDEN_SQL:
            if re.search(rf"\b{kw}\b", head):
                return False, f"Forbidden keyword: {kw}"
        return True, stripped

    def _run_sql(self, query, allow_history=False):
        """Execute a validated read-only statement. Returns a dict suitable as a tool response."""
        ok, cleaned = self._validate_sql(query, allow_history)
        if not ok:
            return {"error": cleaned, "rows": []}
        try:
            columns, rows = run_query(cleaned)
        except Exception as e:  # surface DB errors back to the model so it can adjust
            return {"error": str(e), "rows": []}
        truncated = len(rows) > MAX_RESULT_ROWS   # cap the rows we hand back to the model
        rows = rows[:MAX_RESULT_ROWS]
        return {
            "columns": list(columns),
            "rows": [[_jsonable(v) for v in row] for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }

    # ------------------------------------------------------------- investigate

    def _tool_loop(self, contents, system_instruction, tool, max_turns,
                   allow_history=False, verbose=False):
        """Let the model call run_sql until it stops (or max_turns). Mutates ``contents``.

        Returns the ground-truth record of every query executed and its outcome.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[tool],
            temperature=0,
            # We drive the tool loop ourselves so we can validate SQL and record a trace.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        executed = []
        for _ in range(max_turns):   # bounded loop; the model stops earlier when it's done
            response = self.client.models.generate_content(
                model=MODEL, contents=contents, config=config
            )
            calls = _function_calls(response)
            if not calls:
                break  # model is done investigating

            # Record the model's turn, then answer each tool call.
            contents.append(response.candidates[0].content)
            tool_parts = []
            for call in calls:
                query = (call.args or {}).get("query", "")
                if verbose:
                    print(f"  run_sql: {query}")
                result = self._run_sql(query, allow_history)
                ok, cleaned = self._validate_sql(query, allow_history)
                executed.append({
                    "sql": cleaned if ok else query,
                    "row_count": result.get("row_count"),
                    "error": result.get("error"),
                })
                if verbose and result.get("error"):
                    print(f"    -> error: {result['error']}")
                elif verbose:
                    print(f"    -> {result.get('row_count')} rows")
                tool_parts.append(
                    types.Part.from_function_response(name="run_sql", response=result)
                )
            # The Gemini API expects function responses under the "user" role.
            contents.append(types.Content(role="user", parts=tool_parts))
        return executed

    def investigate(self, question, verbose=False):
        """Run the full investigation and return the structured JSON answer (dict)."""
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=question)])]
        executed = self._tool_loop(
            contents,
            SYSTEM_INSTRUCTION.format(documentation=self.documentation),
            self._tool,
            MAX_SQL_CALLS,
            verbose=verbose,
        )
        answer = self._synthesize(question, contents, executed)
        answer["queries"] = executed
        return answer

    # ------------------------------------------------------------------- RCA

    def run_rca(self, tracking, verbose=False):
        """Explain WHY a tracked entity is missing/stuck. Returns the structured RCA (dict).

        ``tracking`` is a completed tracking result (question, entity, status, summary,
        trace[], root_cause, queries[]). Raises ValueError if it is not RCA-eligible.
        """
        gap = rca_eligibility(tracking)
        if not gap["eligible"]:
            raise ValueError(gap["reason"])

        tracking_json = json.dumps({
            "question": tracking.get("question"),
            "entity": tracking.get("entity"),
            "status": tracking.get("status"),
            "summary": tracking.get("summary"),
            "trace": tracking.get("trace"),
            "suspected_cause_from_tracking": tracking.get("root_cause"),
            "gap": {k: v for k, v in gap.items() if k != "eligible"},
            "tracking_queries": [
                {"sql": q.get("sql"), "row_count": q.get("row_count"), "error": q.get("error")}
                for q in (tracking.get("queries") or []) if isinstance(q, dict)
            ],
        }, indent=2, default=str)

        prompt = (
            "Run a root cause analysis for this tracking result. Explain why the entity is "
            f"{gap['verdict'].lower()} at {gap.get('gap_layer')}.\n\n{tracking_json}"
        )
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        executed = self._tool_loop(
            contents,
            RCA_SYSTEM_INSTRUCTION.format(documentation=self.rca_documentation),
            self._rca_tool,
            MAX_RCA_SQL_CALLS,
            allow_history=True,
            verbose=verbose,
        )

        findings = self._findings_text(contents) or "(no RCA queries were run)"
        response = self.client.models.generate_content(
            model=MODEL,
            contents=RCA_SYNTHESIS_INSTRUCTION.format(
                tracking=tracking_json, findings=findings, documentation=self.rca_documentation
            ),
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json"
            ),
        )
        parsed = _extract_json(response.text)
        if not isinstance(parsed, dict):
            parsed = {
                "entity": tracking.get("entity"),
                "verdict": "INCONCLUSIVE",
                "confidence": "LOW",
                "category": "UNKNOWN",
                "failing_stage": {
                    "from_layer": gap.get("last_present_layer"),
                    "to_layer": gap.get("gap_layer"),
                    "table": gap.get("gap_table"),
                    "transformation": None,
                },
                "summary": "The RCA agent could not produce a structured answer.",
                "root_cause": None,
                "evidence": [],
                "hypotheses": [],
                "pipeline_status": None,
                "missing_evidence": [],
                "next_checks": [],
                "raw": (response.text or "")[:2000],
            }
        parsed["gap"] = {k: v for k, v in gap.items() if k != "eligible"}
        parsed["queries"] = executed
        return parsed

    def _synthesize(self, question, contents, executed):
        """Turn the collected findings into one clean JSON object."""
        findings = self._findings_text(contents) or "(no queries were run)"
        prompt = SYNTHESIS_INSTRUCTION.format(
            question=question, findings=findings, documentation=self.documentation
        )
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json"
            ),
        )
        parsed = _extract_json(response.text)
        if not isinstance(parsed, dict):
            return {
                "question": question,
                "status": "ERROR",
                "summary": "The agent could not produce a structured answer.",
                "entity": {"type": None, "id": None},
                "trace": [],
                "root_cause": None,
                "raw": (response.text or "")[:2000],
            }
        return parsed

    def _findings_text(self, contents):
        """Flatten the SQL calls and their results from the conversation for synthesis."""
        lines = []
        pending_sql = []
        for content in contents:
            for part in content.parts or []:
                fc = getattr(part, "function_call", None)
                fr = getattr(part, "function_response", None)
                if fc and fc.name == "run_sql":
                    pending_sql.append((fc.args or {}).get("query", ""))
                elif fr and fr.name == "run_sql":
                    sql = pending_sql.pop(0) if pending_sql else "(unknown)"
                    lines.append(f"SQL: {sql}\nRESULT: {json.dumps(fr.response, default=str)}")
        return "\n\n".join(lines)


# ---------------------------------------------------------------------- helpers

def _function_calls(response):
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return []
    return [p.function_call for p in parts if getattr(p, "function_call", None)]


def _sql_tool(description, query_description):
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="run_sql",
            description=description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description=query_description)
                },
                required=["query"],
            ),
        )
    ])


def _jsonable(value):
    """Make DB cell values JSON-serialisable (dates, decimals, etc. -> str)."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "...(truncated)"


def _extract_json(text):
    if not text:
        return None
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(candidate[start:end + 1])
        except Exception:
            return None
    return None


def main():
    args = sys.argv[1:]
    with_rca = "--rca" in args
    question = " ".join(a for a in args if a != "--rca").strip()
    agent = DataAgent()
    if question:
        result = agent.investigate(question, verbose=True)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        if with_rca:
            gap = rca_eligibility(result)
            if not gap["eligible"]:
                print(f"\nRCA not applicable: {gap['reason']}")
                return
            print("\nRunning RCA...")
            rca = agent.run_rca({**result, "question": question}, verbose=True)
            print(json.dumps(rca, indent=2, default=str, ensure_ascii=False))
        return
    print("Data investigation agent. Type a question (or 'quit').\n")
    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue
        result = agent.investigate(question, verbose=True)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
