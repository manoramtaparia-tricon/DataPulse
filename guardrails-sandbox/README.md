# Presidio Sandbox

This folder is a small, isolated Python harness for checking how Microsoft Presidio can be used before wiring the checks into the Diagnosis Agent POC.

It is intentionally separate from `backend/` and `frontend/` so you can validate prompt safety, PII detection, and diagnosis output rules without touching the app code.

## What it checks

- Structured diagnosis output.
- Schema validation for required fields and value types.
- Presidio-based PII detection for user prompts and diagnosis text.
- Presidio-based prompt-injection phrase detection for test prompts.
- Presidio-based output redaction so sensitive values can be masked before display.

## Files

- `diagnosis_guardrails_demo.py` - runnable demo with sample prompts and sample model outputs.
- `sample_cases.json` - example prompt/response pairs for quick testing.
- `requirements.txt` - Python dependencies for the sandbox.

## Run it

```bash
pip install -r requirements.txt
python diagnosis_guardrails_demo.py
```

## How this maps to the POC

The POC should treat pipeline logs and user prompts as untrusted input, require evidence for root-cause claims, and reject diagnosis output that does not match the schema.

This sandbox demonstrates that flow with a small set of examples using Presidio for the text-risk checks and Pydantic for the structured output checks.