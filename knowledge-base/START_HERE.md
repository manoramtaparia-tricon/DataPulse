# CMS Hospital Pipeline Knowledge Base

## Purpose

This knowledge base helps a developer or an AI model understand the CMS hospital risk pipeline and investigate failed pipeline runs.

The first version is read-only. It explains the project, identifies the stage where a run failed, shows the evidence, and suggests the next check. It does not change code, rerun jobs, modify tables, or create pull requests.

## Current system

The verified project flow is:

```text
CMS Provider Data API
    -> raw CSV files in a Databricks volume
    -> Bronze Delta tables
    -> Bronze quality gate
    -> Silver dataset tables
    -> Silver hospital_summary table
    -> Gold hospital_risk_report table
    -> Databricks SQL alert
```

The project uses five CMS datasets:

- Hospital General Information
- Hospital Readmissions
- Healthcare-Associated Infections
- Complications and Deaths
- HCAHPS patient experience

## Scope boundary

This knowledge base documents the implementation that exists in this repository. The following are not current project components and must not be described as if they already exist:

- A product-creation UI
- Product APIs or application services
- Kafka or other event brokers
- Kubernetes services
- Product databases
- Automatic code changes
- Automatic job reruns
- Pull-request creation

Those ideas may be future design options, but they are outside the current evidence base.

## Truth labels

Every important statement should use one of these meanings:

- **Verified:** directly supported by source code, configuration, a table schema, or a documented runtime result.
- **Runtime observation:** observed from a particular job run, log, query, or CMS response.
- **Inferred:** a reasonable conclusion supported by multiple facts but not directly recorded.
- **Known gap:** information that the project does not currently record or document.
- **Assumption:** a working assumption that still needs confirmation.
- **Future design:** a proposed capability, not current behavior.

## Source priority

When evidence conflicts, use this order:

1. Current runtime evidence and query results
2. Current table schemas and Databricks job results
3. Versioned source code and configuration
4. Tests and notebooks
5. Reviewed Markdown explanations
6. Assumptions and future design

If two sources conflict, report the conflict. Do not silently choose a convenient explanation.

## How to use this knowledge base

Start with these documents:

1. [System overview](system-overview.md)
2. [Execution and dependencies](execution-and-dependencies.md)
3. [Datasets and contracts](datasets-and-contracts.md)
4. [Lineage](lineage.md)
5. [Business rules](business-rules.md)
6. [Failure catalog](failure-catalog.md)
7. [Runbooks](runbooks.md)
8. [RCA agent playbook](rca-agent-playbook.md)

Use [source index](source-index.md) to find the code or configuration behind a claim.

## First investigation workflow

For a failed pipeline run:

1. Identify the Databricks job run and failed task.
2. Place the task in the pipeline order.
3. Read the task logs and capture the first meaningful error.
4. Check whether the previous stage produced its expected output.
5. Check schema, row count, freshness, nulls, and duplicates as appropriate.
6. Compare the evidence with the failure catalog and runbooks.
7. Report the failing stage, evidence, ranked hypotheses, missing evidence, and next check.

A model should say "failing stage" when that is all the evidence proves. It should say "supported root cause" only when the evidence supports the mechanism. Otherwise it should report ranked hypotheses.

## Current limitations

The repository has useful logging and quality checks, but it does not yet provide a durable incident packet containing every run, task, log, schema, count, and data-quality result. Runtime investigation may therefore require several separate Databricks queries or exports.

The current project also has known documentation gaps around formal lineage, freshness enforcement, schema contracts, structured run correlation, data-quality baselines, and alert context.

## Document status

This is the initial knowledge-base implementation. Facts should be reviewed against the repository and the live Databricks workspace before being used for production incident decisions.
