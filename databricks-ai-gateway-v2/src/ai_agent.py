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
    from src.prompts import SYSTEM_INSTRUCTION, SYNTHESIS_INSTRUCTION
except ImportError:  # allow running the file directly without the package
    from db_connection import run_query
    from prompts import SYSTEM_INSTRUCTION, SYNTHESIS_INSTRUCTION


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_DOC_FILES = ["AGENT_CONTEXT.md"]

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_RESULT_ROWS = 50          # cap rows returned to the model per query
MAX_SQL_CALLS = 12            # runaway guard: the model decides when to stop, this just caps it

FORBIDDEN_SQL =["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "MERGE", "GRANT", "REVOKE"]


class DataAgent:
    def __init__(self, doc_files=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (check your .env).")
        self.client = genai.Client(api_key=api_key)
        self.documentation = self._load_documentation(doc_files)
        self._tool = types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="run_sql",
                description=(
                    "Run a single read-only SELECT query against the data platform and "
                    "return up to %d rows. Use documented table and column names only." % MAX_RESULT_ROWS
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="A single SELECT (or WITH ... SELECT) statement. No DDL/DML.",
                        )
                    },
                    required=["query"],
                ),
            )
        ])

    # ------------------------------------------------------------------ docs

    def _load_documentation(self, doc_files):
        if doc_files is None:
            env = os.getenv("DOC_FILES")
            doc_files = [p.strip() for p in env.split(",")] if env else DEFAULT_DOC_FILES
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

    def _validate_sql(self, query):
        stripped = query.strip().rstrip(";").strip()
        if not stripped:
            return False, "Empty query."
        head = stripped.upper()
        if not (head.startswith("SELECT") or head.startswith("WITH")):
            return False, "Only SELECT queries are allowed."
        for kw in FORBIDDEN_SQL:
            if re.search(rf"\b{kw}\b", head):
                return False, f"Forbidden keyword: {kw}"
        return True, stripped

    def _run_sql(self, query):
        """Execute a validated SELECT. Returns a dict suitable as a tool response."""
        ok, cleaned = self._validate_sql(query)
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

    def investigate(self, question, verbose=False):
        """Run the full investigation and return the structured JSON answer (dict)."""
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=question)])]
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION.format(documentation=self.documentation),
            tools=[self._tool],
            temperature=0,
            # We drive the tool loop ourselves so we can validate SQL and record a trace.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        executed = []  # ground-truth record of every query and its result
        for _ in range(MAX_SQL_CALLS):   # bounded loop; the model stops earlier when it's done
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
                result = self._run_sql(query)
                executed.append({
                    "sql": self._validate_sql(query)[1] if query else query,
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

        answer = self._synthesize(question, contents, executed)
        answer["queries"] = executed
        return answer

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


def _jsonable(value):
    """Make DB cell values JSON-serialisable (dates, decimals, etc. -> str)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


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
    question = " ".join(sys.argv[1:]).strip()
    agent = DataAgent()
    if question:
        result = agent.investigate(question, verbose=True)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
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
