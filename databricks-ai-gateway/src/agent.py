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
from src import prompts

MAX_RESULT_ROWS = 50
MAX_LINEAGE_STEPS = 6  # runaway guard; when to stop is decided by the model, not here

# Decline text for non-lineage questions (this agent is lineage-only).
UNSUPPORTED_MESSAGE = (
    "This agent only answers data lineage questions — tracing whether a specific "
    "customer, order, or product flows through the Bronze, Silver, and Gold layers. "
    'Try a question like "Is customer 42 present in all layers?" or '
    '"Where did order 1234 get stuck?"'
)

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
        return self._unsupported()

    def _unsupported(self):
        """Return a decline response for any question that is not entity lineage."""
        return {"mode": "unsupported", "data": None, "text": UNSUPPORTED_MESSAGE, "detail": ""}

    def _classify(self, question):
        prompt = prompts.CLASSIFY.format(readme=self.readme, question=question)
        return self._extract_json(self._call_gemini(prompt))

    def _investigate_lineage(self, question, info):
        entity_type = info.get("entity_type")
        entity_value = info.get("entity_value")
        entity_label = info.get("entity_label") or f"{entity_type or 'entity'} {entity_value}"

        print(f"  Tracing {entity_label} across layers...")

        # Model picks the next layer to check or stops; we just run its SQL and feed results back.
        stages = []
        executed = []
        for _ in range(MAX_LINEAGE_STEPS):
            decision = self._next_lineage_step(entity_type, entity_value, stages)
            if not isinstance(decision, dict) or decision.get("action") != "query":
                break
            sql = (decision.get("sql") or "").strip().rstrip(";")
            valid, _ = self._validate_sql(sql)
            if not valid:
                break

            print(f"  Checking {decision.get('stage')} ({decision.get('table')})...")
            columns, rows, status = self._run_sql(sql)
            count, last_seen = None, None
            if rows:
                try:
                    count = int(rows[0][0])
                except (ValueError, TypeError, IndexError):
                    count = None
                if len(rows[0]) > 1 and rows[0][1] is not None:
                    last_seen = str(rows[0][1])
            stages.append({
                "stage": decision.get("stage"),
                "layer": decision.get("layer"),
                "table": decision.get("table"),
                "detail": decision.get("detail"),
                "sql": sql,
                "count": count,
                "last_seen": last_seen,
                "error": None if count is not None else status,
            })
            executed.append(
                f"--- {decision.get('stage')} ({decision.get('table')}) ---\n"
                f"SQL: {sql}\nRESULT: count={count}, last_seen={last_seen} {status}"
            )

        if not stages:
            print("  Could not trace this entity.\n")
            return self._unsupported()

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

    def _next_lineage_step(self, entity_type, entity_value, stages):
        """Ask the model for the next trace action: {"action": "query"...} or {"action": "stop"}."""
        if stages:
            steps_so_far = "\n".join(
                f"- {s['stage']} ({s['table']}): count={s['count']}, last_seen={s['last_seen']}"
                for s in stages
            )
        else:
            steps_so_far = "(none yet — start with the first layer)"
        prompt = prompts.LINEAGE_STEP.format(
            readme=self.readme,
            entity_type=entity_type,
            entity_value=entity_value,
            steps_so_far=steps_so_far,
        )
        return self._extract_json(self._call_gemini(prompt))

    def _build_timeline(self, stages):
        # Label each checked layer: Found, Stuck (first gap after a hit), Not found, or Error.
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
        prompt = prompts.EXPLAIN_LINEAGE.format(
            readme=self.readme,
            pipeline_code=self.pipeline_code,
            question=question,
            entity_label=entity_label,
            overall=overall,
            trace=trace,
        )
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


def main():
    print("=" * 60)
    print("  E-Commerce Data Platform — AI Investigation Agent")
    print("  Medallion Architecture: Bronze → Silver → Gold")
    print("=" * 60)
    print()

    agent = Agent()

    print("Ask a lineage question about a specific entity (type 'quit' to exit)")
    print("Examples:")
    print('  "Is customer 42 present in all layers?"')
    print('  "Where did order 1234 get stuck?"')
    print('  "Trace product 7 across Bronze, Silver, and Gold"')
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
            print(f"\n{result['text']}")


if __name__ == "__main__":
    main()
