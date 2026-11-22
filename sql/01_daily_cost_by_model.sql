-- Daily cost per model, from the Cloud Billing detailed (resource-level) export.
-- Billing knows what each model cost. It does not know who used it.
CREATE OR REPLACE TABLE `${OUT_DATASET}.daily_cost_by_model`
PARTITION BY usage_date
AS
WITH lines AS (
  SELECT
    DATE(usage_start_time, '${TIMEZONE}') AS usage_date,
    project.id AS project_id,
    -- The model name is the part of the SKU description before the token type,
    -- for example "Gemini 2.5 Flash Input - Text Input - Predictions".
    COALESCE(
      REGEXP_EXTRACT(
        sku.description,
        r'(?i)\b((?:gemini|claude)[a-z0-9. -]*?)(?:\s+-\s+|\s+(?:input|output|cache|cached|batch|long|predictions?|prompt|text|image|audio|video|tokens?)\b|$)'
      ),
      REGEXP_EXTRACT(service.description, r'(?i)^((?:gemini|claude)[a-z0-9. -]*)$'),
      'Other Vertex AI'
    ) AS model_name,
    CASE
      WHEN LOWER(sku.description) LIKE '%cache%' THEN 'cache'
      WHEN LOWER(sku.description) LIKE '%output%' THEN 'output'
      WHEN LOWER(sku.description) LIKE '%input%' THEN 'input'
      ELSE 'other'
    END AS token_kind,
    cost,
    -- credits is a repeated field of negative amounts
    IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0) AS credit_amount,
    usage.amount_in_pricing_units AS usage_amount,
    usage.pricing_unit AS usage_unit
  FROM `${BILLING_TABLE}`
  WHERE usage_start_time >= TIMESTAMP('${START_DATE}', '${TIMEZONE}')
    AND project.id = '${PROJECT_ID}'
    AND (service.description = 'Vertex AI' OR seller_name = 'Anthropic')
)
SELECT
  usage_date,
  project_id,
  model_name,
  -- Lowercase, non-alphanumerics to "-": "Gemini 2.5 Flash" -> "gemini-2-5-flash".
  -- The audit query builds the same key from the resource name.
  TRIM(REGEXP_REPLACE(LOWER(model_name), r'[^a-z0-9]+', '-'), '-') AS model_key,
  token_kind,
  usage_unit,
  SUM(usage_amount) AS usage_amount,
  SUM(cost) AS cost,
  SUM(cost) + SUM(credit_amount) AS net_cost
FROM lines
GROUP BY usage_date, project_id, model_name, model_key, token_kind, usage_unit;
