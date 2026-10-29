"""Thin HTTP layer that serves the generic DataAgent to the Angular UI.
The frontend calls POST http://localhost:3001/api/diagnose and renders a
TrackingResponse ({title, customerId, timeline[], summary, actions}). This module
runs the agent and maps its generic output onto that UI contract. All the mapping
here is *presentation only* — no investigation logic lives in this file.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from src.ai_agent import DataAgent
except ImportError:
    from ai_agent import DataAgent

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


class DiagnoseRequest(BaseModel):
    question: str


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


def to_ui_shape(result, question):
    entity = result.get("entity") or {}
    entity_id = entity.get("id")
    label = str(entity_id) if entity_id not in (None, "") else "Result"
    return {
        "title": f"{label} - Tracking Results",
        "customerId": label,
        "question": question,
        "timeline": _timeline_from_trace(result.get("trace")),
        "summary": {
            "status": result.get("status") or "UNKNOWN",
            "message": result.get("summary") or "",
        },
        "actions": [
            {"label": "Run RCA Analysis", "tone": "primary"},
            {"label": "View Executed Queries", "tone": "secondary"},
        ],
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
