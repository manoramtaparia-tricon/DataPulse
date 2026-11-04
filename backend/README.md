# Backend

This folder contains the Node.js API used by the DataPulse chat experience.

## Prerequisites

- Node.js installed

## Install

From this folder, install dependencies if you add any in the future:

```powershell
npm install
```

## Run

Start the backend server:

```powershell
npm start
```

The server listens on port `3001` by default.

## API

- `POST /api/diagnose`

Example request body:

```json
{
  "projectTitle": "Customer Data Platform",
  "question": "Where is customer C123? Why is it not in the Gold table?"
}
```

The response returns the tracking data shown in the UI, including an `rca` block
(`{eligible, verdict, reason, context}`).

- `POST /api/rca`: body `{"context": <rca.context from /api/diagnose>}`. Returns a mock
  root cause analysis in the same shape as the Python agent (`databricks-ai-gateway-v2`).

This backend is a mock. The real agent lives in `databricks-ai-gateway-v2/src/ui_api.py`.
