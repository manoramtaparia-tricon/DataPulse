# RCA Agent Playbook

## Mission

Investigate a failed CMS hospital pipeline run using project documentation and read-only runtime evidence. Identify the earliest failing stage, explain what is proven, rank possible mechanisms, and recommend the next safe check.

## Safety boundaries

The model may:

- Read repository files
- Read source symbols and configuration
- Read Databricks job, task, schema, table, query, and log evidence when access exists
- Read CMS metadata and release information
- Recommend checks and remediation ideas

The model may not:

- Modify source code
- Modify or delete data
- Rerun jobs
- Change infrastructure or permissions
- Create pull requests
- Claim that future UI, services, Kafka, Kubernetes, or PR automation exists
- Expose secrets or credentials

## Investigation order

1. Identify the incident, job, and run.
2. Identify the first failed task and map it to a stage.
3. Read the task error and surrounding logs.
4. Confirm the expected input and output for the stage.
5. Check the previous stage’s output.
6. Inspect the relevant contract, lineage, and business rule.
7. Run the smallest read-only check that distinguishes likely causes.
8. Compare the result with the failure catalog and runbook.
9. Produce the structured report below.

## Evidence discipline

For every important claim, provide:

- Evidence source
- Evidence timestamp when available
- Whether it is runtime-observed or source-defined
- What the evidence proves
- What it does not prove

When sources conflict, show both sources and describe the conflict.

## Confidence policy

Use these labels:

- **High:** direct runtime evidence identifies the failure mechanism and no material contradiction is known.
- **Medium:** the failing stage is clear, but the exact mechanism needs one more check.
- **Low:** the result is based mainly on symptoms, incomplete logs, or static assumptions.

Use `supported root cause` only for High confidence evidence. Otherwise use `ranked hypothesis`.

## Required response format

```markdown
# Pipeline Run Investigation

## Incident

- Job:
- Run:
- Reported at:
- Code revision:
- Evidence availability:

## Timeline

1. [time] event and source
2. [time] event and source

## Stage status

| Stage | Status | Evidence | Reference |
|---|---|---|---|
| Ingestion | Found/Missing/Failed/Unknown | ... | ... |
| Bronze | Found/Missing/Failed/Unknown | ... | ... |
| Quality gate | Passed/Failed/Unknown | ... | ... |
| Silver | Found/Missing/Failed/Unknown | ... | ... |
| Joined Silver | Found/Missing/Failed/Unknown | ... | ... |
| Gold | Found/Missing/Failed/Unknown | ... | ... |
| Alerting | Sent/Not sent/Unknown/Not reached | ... | ... |

## Failing stage

State the earliest failing stage and the evidence that localizes it.

## Supported root cause

Only complete this section when the evidence supports the mechanism. Otherwise write `Not established`.

## Ranked hypotheses

1. Hypothesis, confidence, supporting evidence, contradictory evidence
2. Hypothesis, confidence, supporting evidence, contradictory evidence

## Missing evidence

- Evidence not available and why it matters

## Next read-only checks

1. Query or inspection step and the result it would distinguish
2. Query or inspection step and the result it would distinguish

## Recommended remediation

Provide recommendation only. Do not claim that a change was implemented or validated.
```

## Common mistakes to avoid

- Calling a Gold symptom the root cause before checking Ingestion, Bronze, and Silver.
- Treating a CMS placeholder as the same as a failed cast.
- Treating a zero new-row Bronze result as a failure without checking whether the release is unchanged.
- Treating a missing measure as a join failure without checking upstream release timing.
- Confusing the project’s computed star rating with the official CMS rating.
- Using the checked-in alert JSON as proof that the live alert is configured correctly.
- Filling an unavailable run ID, schema, or log with a guess.
- Reporting future architecture as current architecture.
