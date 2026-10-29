"""Thin HTTP layer that serves the generic DataAgent to the Angular UI.
The frontend calls POST http://localhost:3001/api/diagnose and renders a
TrackingResponse ({title, customerId, timeline[], summary, actions}). This module
runs the agent and maps its generic output onto that UI contract. All the mapping
here is *presentation only* — no investigation logic lives in this file.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from src.ai_agent import DataAgent
    from src.guardrails_service import GuardrailBlocked, GuardrailUnavailable, GuardrailsService
except ImportError:
    from ai_agent import DataAgent
    from guardrails_service import GuardrailBlocked, GuardrailUnavailable, GuardrailsService

logger = logging.getLogger(__name__)
app = FastAPI(title="DataPulse Generic Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = None
guardrails = None


@app.on_event("startup")
def _startup():
    global agent, guardrails
    agent = DataAgent()
    guardrails = GuardrailsService(agent.client)


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
async def diagnose(req: DiagnoseRequest):
    question = (req.question or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"message": "question is required"})
    if len(question) > 4000:
        return JSONResponse(status_code=400, content={"message": "question must be 4000 characters or fewer"})
    try:
        if agent is None or guardrails is None:
            raise GuardrailUnavailable("Safety checks unavailable")
        await guardrails.check_input(question)
        result = agent.investigate(question)
        response = to_ui_shape(result, question)
        await guardrails.check_output(result, response)
        return response
    except GuardrailBlocked as error:
        return JSONResponse(
            status_code=403,
            content={
                "message": "I don't have permission to provide this content.",
                "code": "GUARDRAIL_BLOCKED",
                "stage": error.stage,
            },
        )
    except GuardrailUnavailable:
        return JSONResponse(
            status_code=503,
            content={
                "message": "Safety checks are temporarily unavailable. Please try again later.",
                "code": "GUARDRAIL_UNAVAILABLE",
            },
        )
    except Exception as error:
        logger.error("DataPulse diagnosis failed (%s)", type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={"message": "Unable to generate the diagnosis response."},
        )
