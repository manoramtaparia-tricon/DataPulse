"""FastAPI service exposing the investigation agent to the UI.

Run from the project root:
    uvicorn src.api:app --port 8001

POST /api/diagnose  {"question": "...", "projectTitle": "..."}  -> tracking JSON
GET  /health
"""

import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.agent import Agent
from src.guardrails_service import GuardrailBlocked, GuardrailUnavailable, GuardrailsService

logger = logging.getLogger(__name__)

app = FastAPI(title="DataPulse Investigation Agent")

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
    agent = Agent()
    guardrails = GuardrailsService(agent.client)


class DiagnoseRequest(BaseModel):
    question: str
    projectTitle: str = "Customer Data Platform"


def to_ui_shape(result, question, project_title):
    """Map the agent's investigate() output to the UI's tracking contract."""
    mode = result.get("mode")
    data = result.get("data") or {}

    if mode == "lineage" and data:
        obj = next(iter(data.values()))
        return {
            "title": obj.get("title"),
            "entityType": obj.get("entityType"),
            "entityId": obj.get("entityId"),
            "customerId": obj.get("entityId"),
            "projectTitle": project_title,
            "question": question,
            "timeline": obj.get("timeline", []),
            "summary": obj.get("summary", {}),
            "actions": obj.get("actions", []),
        }

    answer = result.get("text") or (data.get("answer", "") if isinstance(data, dict) else "")
    return {
        "title": "Analysis",
        "entityType": None,
        "entityId": None,
        "customerId": None,
        "projectTitle": project_title,
        "question": question,
        "timeline": [],
        "summary": {"status": "ANSWER", "message": answer},
        "actions": [],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/diagnose")
async def diagnose(req: DiagnoseRequest):
    question = (req.question or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"message": "question is required"})
    if len(question) > 4000 or len(req.projectTitle) > 200:
        return JSONResponse(status_code=400, content={
            "message": "Use a question of at most 4000 characters and a project title of at most 200 characters."
        })
    try:
        await guardrails.check_input(question, req.projectTitle)
        result = await run_in_threadpool(agent.investigate, question)
        response = to_ui_shape(result, question, req.projectTitle)
        await guardrails.check_output(result, response)
        return response
    except GuardrailBlocked as error:
        message = (
            "I don't have any context about this."
            if error.stage == "input" else
            "The agent response was blocked by the safety policy and has not been displayed. "
            "Please rephrase your data-platform question."
        )
        return JSONResponse(status_code=403, content={
            "message": message, "code": "GUARDRAIL_BLOCKED", "stage": error.stage
        })
    except GuardrailUnavailable:
        return JSONResponse(status_code=503, content={
            "message": "Safety checks are temporarily unavailable. No unchecked response was returned. Please try again.",
            "code": "GUARDRAIL_UNAVAILABLE",
        })
    except Exception as e:
        logger.error("Diagnosis failed (%s)", type(e).__name__)
        return JSONResponse(
            status_code=500,
            content={"message": "Unable to generate the diagnosis response."},
        )
