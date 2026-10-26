"""FastAPI service exposing the investigation agent to the UI.

Run from the project root:
    uvicorn src.api:app --port 8000

POST /api/diagnose  {"question": "...", "projectTitle": "..."}  -> tracking JSON
GET  /health
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import Agent

app = FastAPI(title="DataPulse Investigation Agent")

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
    agent = Agent()


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

    # Any non-lineage question is declined — this agent only traces entity lineage.
    message = result.get("text") or ""
    return {
        "title": "Unsupported question",
        "entityType": None,
        "entityId": None,
        "customerId": None,
        "projectTitle": project_title,
        "question": question,
        "timeline": [],
        "summary": {"status": "UNSUPPORTED", "message": message},
        "actions": [],
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
        return to_ui_shape(result, question, req.projectTitle)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Unable to generate the diagnosis response.", "error": str(e)},
        )
