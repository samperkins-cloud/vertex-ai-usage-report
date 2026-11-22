-- Daily calls per person, model and region, from Vertex AI data-access audit logs.
-- Audit logs know who called which model. They do not carry token counts for
-- streaming Claude calls, so this counts calls, not tokens.
CREATE OR REPLACE TABLE `${OUT_DATASET}.daily_calls_by_person`
PARTITION BY usage_date
AS
WITH calls AS (
  SELECT
    DATE(timestamp, '${TIMEZONE}') AS usage_date,
    LOWER(protopayload_auditlog.authenticationInfo.principalEmail) AS principal_email,
    REGEXP_EXTRACT(protopayload_auditlog.methodName, r'([^.]+)$') AS method,
    REGEXP_EXTRACT(protopayload_auditlog.resourceName, r'/models/([^/:@]+)') AS model,
    REGEXP_EXTRACT(protopayload_auditlog.resourceName, r'/locations/([^/]+)/') AS location
  FROM `${AUDIT_DATASET}.${AUDIT_TABLE}`
  WHERE timestamp >= TIMESTAMP('${START_DATE}', '${TIMEZONE}')
    AND protopayload_auditlog.serviceName = 'aiplatform.googleapis.com'
    AND IFNULL(protopayload_auditlog.status.code, 0) = 0
)
SELECT
  usage_date,
  principal_email,
  method,
  model,
  -- Same key as the billing query. Drops a trailing version such as -001 or -20250929.
  TRIM(
    REGEXP_REPLACE(LOWER(REGEXP_REPLACE(model, r'-(\d{3}|\d{8})$', '')), r'[^a-z0-9]+', '-'),
    '-'
  ) AS model_key,
  location,
  COUNT(*) AS calls
FROM calls
WHERE LOWER(method) IN ('generatecontent', 'streamgeneratecontent', 'rawpredict', 'streamrawpredict')
GROUP BY usage_date, principal_email, method, model, model_key, location;
