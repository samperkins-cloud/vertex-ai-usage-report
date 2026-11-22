# Setup

Four things to turn on, then three scheduled queries. Replace the all-caps names with your own.

| Name | Example |
|---|---|
| `PROJECT_ID` | the project whose Vertex AI usage you want to report |
| `BILLING_ACCOUNT_ID` | `XXXXXX-XXXXXX-XXXXXX` |
| `BILLING_DATASET` | dataset for the billing export |
| `AUDIT_DATASET` | dataset for the audit log sink |
| `OUT_DATASET` | dataset for the output tables |

Create the three datasets first, all in the same location (such as `US`). The scheduled queries read from two and write to the third, and BigQuery won't query across locations.

## 1. Turn on Data Access audit logs for Vertex AI

Admin Activity logs are always on. Data Access logs, which carry the `GenerateContent` and `RawPredict` calls, are off until you enable them. Logs only start from the day you do this.

```
gcloud projects get-iam-policy PROJECT_ID --format=json > policy.json
```

Add an `auditConfigs` entry to `policy.json`. Leave `bindings` and `etag` alone.

```
"auditConfigs": [
  {
    "service": "aiplatform.googleapis.com",
    "auditLogConfigs": [
      { "logType": "DATA_READ" },
      { "logType": "DATA_WRITE" }
    ]
  }
]
```

If the policy already has an `auditConfigs` list, add this entry to it. Then write it back:

```
gcloud projects set-iam-policy PROJECT_ID policy.json
```

`DATA_READ` is the one that matters here. The inference methods are logged under it. These logs add to your Cloud Logging volume, so check the cost.

Reading the logs in Logs Explorer needs the Private Logs Viewer role (`roles/logging.privateLogViewer`).

## 2. Send the logs to BigQuery

Create a sink that routes only Vertex AI data-access logs to the audit dataset.

```
gcloud logging sinks create vertex-audit-to-bq \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/AUDIT_DATASET \
  --project=PROJECT_ID \
  --log-filter='log_id("cloudaudit.googleapis.com/data_access") AND protoPayload.serviceName="aiplatform.googleapis.com"'
```

The sink gets its own writer identity. Find it and give it access to the dataset:

```
gcloud logging sinks describe vertex-audit-to-bq --project=PROJECT_ID --format='value(writerIdentity)'
```

Grant that identity `roles/bigquery.dataEditor` on the audit dataset. The Logging docs also list `roles/logging.logWriter` for the writer identity.

### Date-sharded or partitioned tables

By default the sink writes one table per day, `cloudaudit_googleapis_com_data_access_YYYYMMDD`. The queries read them with a wildcard, which is the default `AUDIT_TABLE` in `render.py`.

To use one partitioned table instead, add `--use-partitioned-tables` to the sink. The table is then named `cloudaudit_googleapis_com_data_access`. Render the queries with `--audit-table cloudaudit_googleapis_com_data_access`. The queries filter on `timestamp`, which both layouts partition on.

The sink only writes new entries. Nothing earlier shows up, so set `--start-date` to the day you created it.

## 3. Turn on the detailed billing export

In the Cloud Console, go to Billing, then Billing export, then the BigQuery export tab. Under "Detailed usage cost", click Edit settings, pick the project and `BILLING_DATASET`, and save.

The table is named `gcp_billing_export_resource_v1_BILLING_ACCOUNT_ID`, with dashes in the account ID changed to underscores. This is the one with `resource.name`. The standard export doesn't have it, and these queries only need the standard fields, so the standard export works too if you already have it. Pass its table name as `--billing-table`.

The export only holds data from the day you turn it on. Costs appear with a delay of a few hours, and credits and adjustments can change a day's numbers later. Rerunning the queries daily picks those up.

## 4. Render the queries

```
python3 render.py \
  --billing-table PROJECT_ID.BILLING_DATASET.gcp_billing_export_resource_v1_BILLING_ACCOUNT_ID \
  --audit-dataset PROJECT_ID.AUDIT_DATASET \
  --out-dataset PROJECT_ID.OUT_DATASET \
  --project-id PROJECT_ID \
  --start-date YYYY-MM-DD \
  --out out
```

Check each one without running it:

```
bq query --use_legacy_sql=false --dry_run < out/01_daily_cost_by_model.sql
```

`--dry_run` prints the bytes the query would scan. Queries 03 and 04 need the tables from 01 and 02 to exist, so run 01 and 02 once by hand first.

## 5. Schedule the queries

Each query creates its own table with a DDL statement, so the scheduled queries need no destination table or dataset. Run these in order. 03 should run after 01 and 02 have finished, so give it a later time.

```
bq mk --transfer_config \
  --project_id=PROJECT_ID \
  --display_name='ai usage: daily cost by model' \
  --schedule='every 24 hours' \
  --data_source=scheduled_query \
  --params="$(python3 -c 'import json,sys; print(json.dumps({"query": sys.stdin.read()}))' < out/01_daily_cost_by_model.sql)"
```

Do the same for `02_daily_calls_by_person.sql` and `03_estimated_cost_by_person.sql`. Query 04 is a view. Create it once with `bq query --use_legacy_sql=false < out/04_calls_by_region_view.sql`.

Notes from the BigQuery docs:

- Avoid starting a schedule exactly on the hour. A time like `09:03` is safer.
- `--schedule` takes values like `'every 24 hours'` or `'every monday 09:03'`. Without it, the default is every 24 hours from creation.
- Add `--service_account_name=SA_EMAIL` to run as a service account instead of your own user.
- The first time you create one as a user, `bq` may ask you to open a URL and paste a code.

## Reading the results

```
SELECT usage_date, principal_email, model_key, calls, est_net_cost
FROM `PROJECT_ID.OUT_DATASET.estimated_cost_by_person`
ORDER BY usage_date DESC, est_net_cost DESC
LIMIT 50;
```

The row with `(no calls logged)` is cost for a model that had no logged calls that day. It's there so the totals still match the bill.
