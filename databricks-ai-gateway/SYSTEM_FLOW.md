# System Flow — Prompt to Result

How a question travels from the UI through the agent and back, and how the agent
uses Gemini and Databricks to answer it.

At startup the agent loads its context once: `DATA_PLATFORM.md` (tables, columns,
keys, lineage), `build_pipeline.py` (transformations), and the prompt templates in
`prompts.py`. Every Gemini call includes this context.

## Sequence diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Angular UI
    participant API as FastAPI /api/diagnose
    participant AG as Agent
    participant G as Gemini
    participant DB as Databricks

    User->>UI: Type question, press Enter
    UI->>API: POST /api/diagnose {question}
    API->>AG: investigate(question)

    Note over AG: Context loaded at startup<br/>DATA_PLATFORM.md + pipeline + prompts

    AG->>G: Classify question (CLASSIFY prompt + docs)
    G-->>AG: mode + entity

    alt Lineage question (e.g. "is customer 42 in all layers?")
        AG->>G: Plan presence checks (PLAN_LINEAGE)
        G-->>AG: One SELECT per layer
        AG->>AG: Validate SQL (SELECT-only guard)
        loop Bronze, Silver, Gold
            AG->>DB: Run presence query
            DB-->>AG: count + last_seen
        end
        AG->>AG: Build timeline (Found / Stuck / Not found)
        AG->>G: Explain outcome (EXPLAIN_LINEAGE)
        G-->>AG: Plain-text summary
    else Not a lineage question
        AG->>AG: Decline (unsupported — lineage questions only)
    end

    AG-->>API: result {mode, data, text}
    API->>API: to_ui_shape() -> UI contract
    API-->>UI: JSON {title, timeline, summary, actions}
    UI->>User: Render timeline + summary
```

## Flowchart

```mermaid
flowchart TD
    U[User types question in UI] --> API[POST /api/diagnose - FastAPI]
    API --> INV[Agent.investigate]
    INV --> CL{Classify via Gemini}

    CL -->|lineage| L1[Plan presence SQL per layer - Gemini]
    L1 --> L2[Validate SELECT-only]
    L2 --> L3[(Run on Databricks<br/>Bronze / Silver / Gold)]
    L3 --> L4[Build timeline<br/>Found / Stuck / Not found]
    L4 --> L5[Explain result - Gemini]

    CL -->|not lineage| D1[Decline<br/>unsupported — lineage questions only]

    L5 --> SHAPE[to_ui_shape -> UI contract JSON]
    D1 --> SHAPE
    SHAPE --> R[Return JSON to UI]
    R --> REN[UI renders timeline + summary]
```
