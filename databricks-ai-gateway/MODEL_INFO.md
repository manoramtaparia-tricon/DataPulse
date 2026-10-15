# Gemini 3.5 Flash-Lite — Model Reference

## Overview

We use **Google Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`) in our AI agent. It is Google's high-efficiency, low-latency model designed for agentic workflows — fast responses at minimal cost.

## Why This Model?

| Criteria | Reason |
|----------|--------|
| **Cost** | One of the cheapest Gemini models — ideal for a POC where the agent makes multiple API calls per question |
| **Speed** | ~350 output tokens/sec (per Artificial Analysis benchmark, cited by Google) — fast enough for live demos |
| **Function calling** | Native support for function calling, structured outputs, and tool use — critical for our SQL generation workflow |
| **Context window** | 1M tokens — large enough to load DATA_PLATFORM.md + pipeline code + all 7 table schemas in a single prompt |
| **Good enough reasoning** | Handles SQL generation and result analysis well for our use case |

## Specifications

| Spec | Value |
|------|-------|
| Model ID | `gemini-3.5-flash-lite` |
| Provider | Google (via `google-genai` SDK) |
| Release Date | July 2026 |
| Context Window | 1,048,576 tokens (~1M tokens / ~1,500 pages) |
| Max Output | 65,536 tokens (~66K) |
| Input Modalities | Text, Image, Video, Audio, PDF |
| Output Modalities | Text |
| Output Speed | ~350 tokens/sec (Artificial Analysis benchmark, cited by Google) |

## Pricing (Pay-as-you-go)

| Tier | Input (per 1M tokens) | Output (per 1M tokens) |
|------|----------------------|------------------------|
| Standard | $0.30 | $2.50 |
| Cached Input | $0.03 | — |
| Batch / Flex | $0.15 | $1.25 |

For reference: processing one agent question with 3-4 queries costs roughly $0.001–$0.003.

## Free Tier (What We Use)

We are using the **free tier** via Google AI Studio API key.

| Limit | Value |
|-------|-------|
| Requests per Minute (RPM) | ~15 |
| Requests per Day (RPD) | ~1,000 |
| Tokens per Minute (TPM) | ~250,000 |
| Cost | $0 |

These limits are sufficient for our POC — each agent question makes 3-6 API calls, so we can handle ~150-300 questions per day on the free tier.

> **Note:** Free tier limits are not officially published per-model by Google and may vary by project. Check your actual limits in Google AI Studio. The numbers above are based on observed limits and third-party documentation.

## Capabilities We Use

- **Text generation** — Generating SQL queries from natural language questions
- **Function calling** — Structured query generation and multi-round investigation
- **Large context** — Loading full project documentation + pipeline code + table schemas (~5K-10K tokens) in every request
- **Reasoning** — Analyzing query results and producing coherent explanations

## Capabilities We Don't Use (Yet)

- **Thinking / configurable reasoning levels** — The model supports minimal, medium, and high reasoning modes; we use the default
- **Vision / multimodal input** — We only send text
- **Code execution** — We handle SQL execution ourselves via `databricks-sql-connector`
- **Search grounding** — Not needed since we query Databricks directly

## Model Comparison

| Model | Input Cost | Output Cost | Speed | Context | Best For |
|-------|-----------|-------------|-------|---------|----------|
| **Gemini 3.5 Flash-Lite** (ours) | $0.30/1M | $2.50/1M | ~350 t/s | 1M | Cost-efficient agentic tasks |
| Gemini 3.5 Flash | $1.50/1M | $9.00/1M | ~250 t/s | 1M | Complex reasoning, harder tasks |
| Gemini 2.0 Flash-Lite | $0.07/1M | $0.30/1M | — | 1M | Ultra-cheap, simpler tasks |

We chose 3.5 Flash-Lite as the sweet spot — significantly better reasoning than 2.0 Flash-Lite (Terminal-Bench: 54% vs 31%) at a fraction of the cost of full 3.5 Flash.

## How It Fits in Our Architecture

```
User Question
    ↓
Agent (Python) sends question + DATA_PLATFORM.md + pipeline code + table schemas → Gemini 3.5 Flash-Lite
    ↓
Gemini generates SQL queries (SELECT only)
    ↓
Agent executes queries on Databricks
    ↓
Agent sends results back → Gemini 3.5 Flash-Lite
    ↓
Gemini generates plain-English analysis
    ↓
Answer displayed to user
```

The model never touches Databricks directly. Our agent acts as the middleware — Gemini thinks, the agent executes.
