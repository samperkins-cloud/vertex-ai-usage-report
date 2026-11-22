-- ESTIMATED cost per person per day.
-- Each model's cost for the day is split by the person's share of that model's
-- calls that day. Billing has no user field, so this is an apportionment, not a
-- billed number.
-- Run after 01 and 02.
CREATE OR REPLACE TABLE `${OUT_DATASET}.estimated_cost_by_person`
PARTITION BY usage_date
AS
WITH cost AS (
  SELECT usage_date, model_key, ANY_VALUE(model_name) AS model_name,
         SUM(cost) AS cost, SUM(net_cost) AS net_cost
  FROM `${OUT_DATASET}.daily_cost_by_model`
  GROUP BY usage_date, model_key
),
calls AS (
  SELECT
    usage_date,
    model_key,
    principal_email,
    SUM(calls) AS calls,
    SUM(SUM(calls)) OVER (PARTITION BY usage_date, model_key) AS model_calls
  FROM `${OUT_DATASET}.daily_calls_by_person`
  GROUP BY usage_date, model_key, principal_email
)
SELECT
  COALESCE(c.usage_date, k.usage_date) AS usage_date,
  COALESCE(c.model_key, k.model_key) AS model_key,
  c.model_name,
  -- Cost with no calls that day (or a model key that did not match) keeps a row
  -- of its own, so the totals still add up to the bill.
  IFNULL(k.principal_email, '(no calls logged)') AS principal_email,
  k.calls,
  SAFE_DIVIDE(k.calls, k.model_calls) AS share_of_model_calls,
  IF(k.principal_email IS NULL, c.cost, c.cost * k.calls / k.model_calls) AS est_cost,
  IF(k.principal_email IS NULL, c.net_cost, c.net_cost * k.calls / k.model_calls) AS est_net_cost,
  'ESTIMATE: model cost split by share of calls' AS note
FROM cost AS c
FULL OUTER JOIN calls AS k
  ON c.usage_date = k.usage_date AND c.model_key = k.model_key;
