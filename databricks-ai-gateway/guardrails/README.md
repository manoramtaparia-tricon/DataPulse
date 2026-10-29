# DataPulse NeMo Guardrails

This directory contains the NeMo Guardrails configuration used by the
DataPulse HTTP API. The guardrails check a user's question before it reaches
the investigation agent and check the agent's result before it is returned to
the UI.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| [`config.yml`](config.yml) | Tells NeMo which rails to run for input and output, and configures the dialog embedding behavior. |
| [`rails.co`](rails.co) | Defines the input and output flows. Each flow calls a named Python action and stops with a standard refusal if the action does not allow the content. |
| [`../src/guardrails_service.py`](../src/guardrails_service.py) | Loads the NeMo configuration, registers the Python actions, applies local checks, asks Gemini to classify content, and turns the result into an allow, block, or unavailable outcome. |

The policy itself is the `POLICY` string in `guardrails_service.py`. It describes
what DataPulse may answer, what must be blocked, and how to treat untrusted
content in records and query results. The `.co` flows are the orchestration;
they do not contain the full domain policy.

## Request flow

```text
POST /api/diagnose
        |
        v
API validates the question
        |
        v
guardrails.check_input(question)
        |
        v
NeMo config selects the input rail
        |
        v
rails.co runs datapulse_check_input
        |
        v
Python service applies local checks, then Gemini classifies the question
        |
   allowed? ---- no ----> stop; API returns HTTP 403
        |
       yes
        v
agent.investigate(question)
        |
        v
API builds the UI response
        |
        v
guardrails.check_output(agent result + UI response)
        |
        v
NeMo config selects the output rail
        |
        v
rails.co runs datapulse_check_output
        |
        v
Python service applies local checks, then Gemini classifies the content
        |
   allowed? ---- no ----> stop; API returns HTTP 403
        |
       yes
        v
API returns the UI response
```

If a classifier call, timeout, invalid verdict, or rail execution fails, the
service raises `GuardrailUnavailable`. The API returns HTTP 503 and does not
return an unchecked response. The guardrails fail closed: uncertain or missing
verdicts never result in content being passed through.

## How the files connect

### `config.yml`

`rails.input.flows` selects `datapulse input policy`, and
`rails.output.flows` selects `datapulse output policy`. Those are the flow names
defined in `rails.co`. `models: []` is intentional: the classifier is called by
the registered Python actions using the shared Google GenAI client rather than
by a NeMo-configured conversational model. The simple embedding provider is
configured for NeMo's dialog handling.

### `rails.co`

The input flow executes `datapulse_check_input`; the output flow executes
`datapulse_check_output`. These names must match the action names registered in
`GuardrailsService.__init__`. Each flow checks `$allowed`. When it is false, the
flow issues the configured refusal and stops. This prevents generation from
continuing after an input rejection and prevents a rejected output from being
passed through.

### `guardrails_service.py`

At API startup, `GuardrailsService` loads the `guardrails/` directory through
`RailsConfig.from_path()` and registers both actions. Each action gets the
message from NeMo's context and calls the shared policy-checking code.

Before content is sent to Gemini, the service:

- Rejects input over 5,000 characters or output over 64,000 characters.
- Scans for common credential patterns and the configured
  `GEMINI_API_KEY` / `DATABRICKS_TOKEN` values, including escaped forms.
- Sends eligible content to Gemini with `POLICY`, temperature `0`, and a
  response schema requiring a boolean `allowed` field.
- Applies a 30-second timeout to the classifier call.

The API currently applies an earlier 4,000-character limit to incoming
questions, so normal HTTP requests hit that limit before the service's 5,000
character input limit. For input classification, the service sends a JSON
object containing the question. For output classification, it checks a JSON
object containing both the raw agent result and the UI response, so sensitive
details cannot slip through just because they are omitted from the displayed
shape.

The classifier model is selected with `GUARDRAILS_MODEL`; if it is unset, the
service uses `gemini-3.5-flash-lite`. The Gemini client is shared with the
agent, so its normal API key configuration is also required.

## Outcomes at the API

- **Allowed:** the input continues to the agent, or the checked output is
  returned to the UI.
- **Policy blocked:** the API returns HTTP 403 with code
  `GUARDRAIL_BLOCKED` and the relevant `input` or `output` stage.
- **Check unavailable:** the API returns HTTP 503 with code
  `GUARDRAIL_UNAVAILABLE`; no unchecked answer is returned.

## Changing the guardrails

- Change the domain allow/block rules in the `POLICY` string in
  `guardrails_service.py`.
- Change which rails are enabled or selected in `config.yml`.
- Change flow behavior in `rails.co`. Keep its `execute` action names aligned
  with the names registered in `GuardrailsService.__init__`.
- If changing a limit, timeout, model default, or local credential check, edit
  the corresponding constant or logic in `guardrails_service.py`.
- Keep the API's exception mapping in `src/api.py` consistent if adding a new
  guardrail outcome.

These checks supplement application authorization and data-access controls;
they do not replace them.