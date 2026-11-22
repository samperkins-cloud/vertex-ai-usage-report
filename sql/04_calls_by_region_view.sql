-- One row per logged call, with the region it was sent to.
-- The location comes from the resource name. "global" means the global
-- endpoint, which does not pin the call to a region.
CREATE OR REPLACE VIEW `${OUT_DATASET}.calls_with_region` AS
SELECT
  timestamp,
  DATE(timestamp, '${TIMEZONE}') AS usage_date,
  LOWER(protopayload_auditlog.authenticationInfo.principalEmail) AS principal_email,
  REGEXP_EXTRACT(protopayload_auditlog.methodName, r'([^.]+)$') AS method,
  REGEXP_EXTRACT(protopayload_auditlog.resourceName, r'/models/([^/:@]+)') AS model,
  REGEXP_EXTRACT(protopayload_auditlog.resourceName, r'/locations/([^/]+)/') AS location,
  IF(
    REGEXP_EXTRACT(protopayload_auditlog.resourceName, r'/locations/([^/]+)/') = 'global',
    'global',
    'regional'
  ) AS endpoint_kind
FROM `${AUDIT_DATASET}.${AUDIT_TABLE}`
WHERE timestamp >= TIMESTAMP('${START_DATE}', '${TIMEZONE}')
  AND protopayload_auditlog.serviceName = 'aiplatform.googleapis.com'
  AND IFNULL(protopayload_auditlog.status.code, 0) = 0
  AND LOWER(REGEXP_EXTRACT(protopayload_auditlog.methodName, r'([^.]+)$'))
      IN ('generatecontent', 'streamgeneratecontent', 'rawpredict', 'streamrawpredict');
