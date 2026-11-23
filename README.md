# vertex-ai-usage-report

BigQuery queries that show how much Vertex AI each person used and roughly what it cost. They join two things Google Cloud already records, with no extra tooling.

Leadership asks the same two questions about AI: who is using it, and what does it cost? Google Cloud has both answers. They sit in different places.

## The two gaps

- **Cloud Billing export.** It knows exactly what each model cost per day. It has no user field, so it can't say who spent it.
- **Vertex AI audit logs.** They know who called which model, with which method, from which region. For Claude's streaming calls (`StreamRawPredict`) they don't record token counts, so you can count calls but not tokens.

The join fills both. Billing gives the cost of each model each day. The audit logs give each person's share of that model's calls that day. Cost times share is an estimate of what that person cost.

```
billing export  ->  daily cost per model  \
                                            ->  estimated cost per person
audit logs      ->  daily calls per person /
```

## What it answers

- What did each model cost per day?
- Who called which model, how often, and from which region?
- Roughly what did each person's usage cost?
- Which region did each call go to?

## What's in the repo

| File | What it does |
|---|---|
| `sql/01_daily_cost_by_model.sql` | Daily cost per model from the detailed billing export, Vertex AI only. The model comes from the SKU description, or from the service name for partner models such as Claude, which bill under their own service. |
| `sql/02_daily_calls_by_person.sql` | Daily calls per person, model, method and region, from the exported audit logs. |
| `sql/03_estimated_cost_by_person.sql` | Each model's daily cost split by each person's share of that model's calls. Labeled as an estimate in the output. |
| `sql/04_calls_by_region_view.sql` | A view with one row per call and the region it went to. Optional. |
| `render.py` | Fills in the `${...}` placeholders and prints or writes the SQL. |
| `docs/setup.md` | Audit logs, the log sink, the billing export and scheduled queries. |

## Quick start

Set up the logs and the export first, following [docs/setup.md](docs/setup.md). Then:

```
python3 render.py \
  --billing-table my-project.billing.gcp_billing_export_resource_v1_XXXXXX_XXXXXX_XXXXXX \
  --audit-dataset my-project.vertex_audit \
  --out-dataset my-project.ai_usage \
  --project-id my-project \
  --start-date 2026-01-01 \
  --out out
```

That writes four `.sql` files to `out/`. Check one without running it:

```
bq query --use_legacy_sql=false --dry_run < out/01_daily_cost_by_model.sql
```

Run 01 and 02, then 03. Setup shows how to schedule them with `bq mk --transfer_config`.

I run the same join at work. These queries are a clean rewrite of it, checked against Google's docs, so dry-run each one in your own project first. Your export may name things a little differently.

Every value can also come from an environment variable with the placeholder's name, such as `BILLING_TABLE`. `--timezone` sets where days are cut and defaults to UTC. `--audit-table` switches to partitioned log tables.

## How the estimate works

For one day and one model, say the model cost $40 and two people called it, three times and one time. The first gets $30 and the second gets $10. A model with cost but no logged calls that day keeps its own row, `(no calls logged)`, so the totals still add up to the bill.

The share is by call count. A call with a huge prompt counts the same as a short one.

## Limits

- Cost per person is an estimate. It assumes every call to a model costs about the same. Rank order is usually fine. Exact dollars aren't.
- Audit logs only exist from the day you turn on Data Access logging and create the sink. Nothing is backfilled.
- Streaming Claude calls log no token counts, so the audit side counts calls only. Token totals come from the billing side, per model, not per person.
- The two sides join on a model name built from the billing SKU text and from the audit resource name. If they don't line up, cost shows up under `(no calls logged)` and the calls show up with no cost. Partner-model SKU names change, and so do model IDs. Check the join after a new model appears, and adjust the regular expressions in 01 and 02.
- The queries don't de-duplicate audit entries. If you see doubled counts, check the sink and the log filter first.
- Calls that failed are left out. Count-tokens and similar methods are left out too, since they bill nothing.
- Cloud Billing numbers can change for a few days after the fact. Credits and adjustments land late. The queries rebuild the tables from the start date each run.
- The region is the one in the resource name the call was sent to. For `global`, the log doesn't say where it was served.

## Tests

```
python3 -m unittest discover -s tests
```

They cover placeholder rendering, no leftover `${...}`, and a plain Python version of the cost split (`costsplit.py`) on sample rows. If `sqlglot` is installed in a local venv, they also parse every query as BigQuery SQL. Without it, that test is skipped. No network.

## Docs these were written against

- [Detailed usage cost data schema](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/detailed-usage)
- [Vertex AI audit logging](https://docs.cloud.google.com/vertex-ai/docs/general/audit-logging)
- [Cloud Audit Logs: AuditLog fields](https://docs.cloud.google.com/logging/docs/reference/audit/auditlog/rest/Shared.Types/AuditLog)
- [Logging: BigQuery schema for routed logs](https://docs.cloud.google.com/logging/docs/export/bigquery)
- [Configure Data Access audit logs](https://docs.cloud.google.com/logging/docs/audit/configure-data-access)
- [gcloud logging sinks create](https://docs.cloud.google.com/sdk/gcloud/reference/logging/sinks/create)
- [Configure and manage sinks](https://docs.cloud.google.com/logging/docs/export/configure_export_v2)
- [Scheduling queries](https://docs.cloud.google.com/bigquery/docs/scheduling-queries)
- [Use Claude on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude)

MIT license.
