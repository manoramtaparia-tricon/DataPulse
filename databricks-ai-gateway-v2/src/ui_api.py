"""Thin HTTP layer that serves the generic DataAgent to the Angular UI.
The frontend calls POST http://localhost:3001/api/diagnose and renders a
TrackingResponse ({title, customerId, timeline[], summary, actions, rca}). When the
tracking verdict is MISSING/STUCK the response carries an ``rca.context`` that the UI
posts back to POST /api/rca to run the root cause analysis. This module runs the agent
and maps its generic output onto that UI contract. All the mapping here is
*presentation only*; no investigation logic lives in this file.
"""

import json

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from src.ai_agent import DataAgent, rca_eligibility
except ImportError:
    from ai_agent import DataAgent, rca_eligibility

app = FastAPI(title="DataPulse Generic Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = None


@app.on_event("startup")
def _startup():
    global agent
    agent = DataAgent()


MAX_RCA_CONTEXT_BYTES = 100_000   # the context is client-echoed; keep it bounded


class DiagnoseRequest(BaseModel):
    question: str


class RcaRequest(BaseModel):
    context: dict


def _timeline_from_trace(trace):
    """Map the agent's trace[] to UI timeline items, labelling tone/status.

    Found -> success. The first layer where the entity is absent *after* it was
    seen earlier is 'Stuck' (warning); any other absence is 'Not found' (muted).
    """
    items = []
    seen_found = False
    stuck_marked = False
    for step in trace or []:
        found = bool(step.get("found"))
        if found:
            status, tone = "Found", "success"
            seen_found = True
        elif seen_found and not stuck_marked:
            status, tone = "Stuck", "warning"
            stuck_marked = True
        else:
            status, tone = "Not found", "muted"
        items.append({
            "stage": step.get("layer") or "--",
            "table": step.get("table") or "",
            "detail": step.get("note") or "",
            "status": status,
            "timestamp": step.get("last_seen") or "--",
            "tone": tone,
        })
    return items


def _rca_block(result, question):
    """Eligibility + the tracking context the UI echoes back to /api/rca.

    Stateless by design: nothing is cached server-side, so RCA keeps working across
    API restarts/reloads. /api/rca re-checks eligibility on whatever it receives.
    """
    gap = rca_eligibility(result)
    if not gap["eligible"]:
        return {"eligible": False, "reason": gap["reason"], "context": None}
    return {
        "eligible": True,
        "verdict": gap["verdict"],
        "reason": gap["reason"],
        "context": {
            "question": question,
            "entity": result.get("entity"),
            "status": result.get("status"),
            "summary": result.get("summary"),
            "trace": result.get("trace"),
            "root_cause": result.get("root_cause"),
            "queries": result.get("queries"),
        },
    }


def to_ui_shape(result, question):
    entity = result.get("entity") or {}
    entity_id = entity.get("id")
    label = str(entity_id) if entity_id not in (None, "") else "Result"
    rca = _rca_block(result, question)
    actions = []
    if rca["eligible"]:
        actions.append({"id": "run_rca", "label": "Run RCA Analysis", "tone": "primary"})
    actions.append({"id": "view_queries", "label": "View Executed Queries", "tone": "secondary"})
    return {
        "title": f"{label} - Tracking Results",
        "customerId": label,
        "question": question,
        "timeline": _timeline_from_trace(result.get("trace")),
        "summary": {
            "status": result.get("status") or "UNKNOWN",
            "message": result.get("summary") or "",
        },
        "actions": actions,
        "rca": rca,
    }


def _as_list(value):
    return value if isinstance(value, list) else []


def to_rca_ui_shape(rca):
    entity = rca.get("entity") or {}
    entity_id = entity.get("id")
    label = str(entity_id) if entity_id not in (None, "") else "Result"
    stage = rca.get("failing_stage") or {}
    return {
        "title": f"{label} - Root Cause Analysis",
        "entity": {"type": entity.get("type"), "id": entity_id},
        "verdict": rca.get("verdict") or "INCONCLUSIVE",
        "confidence": rca.get("confidence") or "LOW",
        "category": rca.get("category") or "UNKNOWN",
        "failingStage": {
            "fromLayer": stage.get("from_layer"),
            "toLayer": stage.get("to_layer"),
            "table": stage.get("table"),
            "transformation": stage.get("transformation"),
        },
        "summary": rca.get("summary") or "",
        "rootCause": rca.get("root_cause"),
        "evidence": _as_list(rca.get("evidence")),
        "hypotheses": _as_list(rca.get("hypotheses")),
        "pipelineStatus": rca.get("pipeline_status"),
        "missingEvidence": _as_list(rca.get("missing_evidence")),
        "nextChecks": _as_list(rca.get("next_checks")),
        "queries": _as_list(rca.get("queries")),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/diagnose")
def diagnose(req: DiagnoseRequest):
    question = (req.question or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"message": "question is required"})
    try:
        result = agent.investigate(question)
        return to_ui_shape(result, question)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Unable to generate the diagnosis response.", "error": str(e)},
        )


@app.post("/api/rca")
def rca(req: RcaRequest):
    context = req.context or {}
    if len(json.dumps(context, default=str)) > MAX_RCA_CONTEXT_BYTES:
        return JSONResponse(status_code=413, content={"message": "RCA context is too large."})
    gap = rca_eligibility(context)
    if not gap["eligible"]:
        # Mirrors the UI rule: RCA only for MISSING/STUCK tracking verdicts.
        return JSONResponse(
            status_code=422,
            content={"message": f"RCA is not applicable: {gap['reason']}", "code": "RCA_NOT_APPLICABLE"},
        )
    try:
        return to_rca_ui_shape(agent.run_rca(context))
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Unable to complete the root cause analysis.", "error": str(e)},
        )
