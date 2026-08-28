# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · GenAI shift-briefing assistant
# MAGIC Meridian Freight Systems. Grounds a Foundation Model (`databricks-claude-sonnet-5`)
# MAGIC in the governed gold tables to generate a concise, actionable **dock shift briefing**
# MAGIC with prioritized staffing moves. Also registers a reusable Unity Catalog SQL
# MAGIC function `generate_shift_brief(...)` (via `ai_query`) that the app and Genie can call.

# COMMAND ----------

import json
S = "fedex_fevm_catalog.dock_ops_chad_macumber"
# Real-time endpoint (best quality) used by the app/notebook via the serving SDK.
ENDPOINT = "databricks-claude-sonnet-5"
# Batch-inference-supported endpoint used by the governed ai_query() UC function
# (the Claude pay-per-token endpoint is not supported by ai_query's batch path).
BATCH_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"

# COMMAND ----------
# DBTITLE 1,Assemble a grounded operational snapshot from gold tables
current = spark.sql(f"""
  SELECT terminal,
    SUM(CASE WHEN telemetry_status='occupied' THEN 1 ELSE 0 END) AS occupied_docks,
    COUNT(*) AS total_docks,
    SUM(CASE WHEN cv_state='obstructed' THEN 1 ELSE 0 END) AS cv_obstructed
  FROM {S}.gold_dock_current_state GROUP BY terminal ORDER BY terminal
""").toPandas()

util = spark.sql(f"""
  SELECT terminal, ROUND(AVG(utilization_pct),1) avg_util,
    ROUND(SUM(detention_fee_usd),0) detention_usd_31d
  FROM {S}.gold_terminal_hourly GROUP BY terminal ORDER BY terminal
""").toPandas()

understaffed = spark.sql(f"""
  SELECT terminal, hour_of_day, MAX(labor_gap) max_gap, MAX(forecast_headcount) fc, MAX(scheduled_headcount) sched
  FROM {S}.gold_staffing_forecast
  WHERE day_of_week NOT IN (1,7) AND labor_gap > 0
  GROUP BY terminal, hour_of_day ORDER BY max_gap DESC LIMIT 8
""").toPandas()

detention_hot = spark.sql(f"""
  SELECT dock_id, ROUND(SUM(detention_fee_usd),0) detention_usd, COUNT(*) visits
  FROM {S}.gold_visit_fact GROUP BY dock_id ORDER BY detention_usd DESC LIMIT 5
""").toPandas()

context = {
    "company": "Meridian Freight Systems (national LTL carrier)",
    "current_dock_status": current.to_dict("records"),
    "utilization_and_detention_31d": util.to_dict("records"),
    "forecast_top_understaffed_weekday_hours": understaffed.to_dict("records"),
    "detention_hotspot_docks": detention_hot.to_dict("records"),
}
context_str = json.dumps(context, indent=2, default=str)
print(context_str)

# COMMAND ----------
# DBTITLE 1,Generate the shift briefing via the Foundation Model (grounded)
prompt = (
    "You are a dock operations advisor for Meridian Freight Systems. Using ONLY the "
    "operational snapshot below (JSON), write a crisp shift briefing for the terminal "
    "supervisors. Include: (1) a one-line situation summary, (2) the top 3 prioritized "
    "staffing/dock actions with the specific terminal, hour, and headcount move, and "
    "(3) the projected impact on detention fees and overtime. Be specific and use the "
    "numbers. Keep it under 220 words.\n\nOPERATIONAL SNAPSHOT:\n" + context_str
)
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

w = WorkspaceClient()
resp = w.serving_endpoints.query(
    name=ENDPOINT,
    messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)],
    max_tokens=600,
)
brief = resp.choices[0].message.content
print("=== GENERATED SHIFT BRIEFING ===\n")
print(brief)

# COMMAND ----------
# DBTITLE 1,Register a reusable, governed UC AI function
spark.sql(f"""
CREATE OR REPLACE FUNCTION {S}.generate_shift_brief(ops_context STRING)
RETURNS STRING
COMMENT 'Generates a dock shift briefing from an operational-snapshot JSON using a Foundation Model.'
RETURN ai_query('{BATCH_ENDPOINT}',
  CONCAT('You are a dock operations advisor for Meridian Freight Systems. From the JSON ',
         'snapshot, write a concise shift briefing with the top 3 prioritized staffing ',
         'actions (terminal, hour, headcount move) and projected impact on detention and ',
         'overtime. Under 220 words.\\n\\n', ops_context))
""")
print("registered UC function generate_shift_brief")

# quick functional check of the UC function on a tiny context
fn_out = spark.sql(f"""SELECT {S}.generate_shift_brief(
  '{{"terminal":"MEM","hour":11,"forecast_headcount":17,"scheduled":8}}') AS b""").collect()[0]["b"]
print("\n=== UC FUNCTION OUTPUT (sample) ===\n", fn_out[:600])

# COMMAND ----------
# DBTITLE 1,Evidence
result = {
    "endpoint": ENDPOINT,
    "grounding_context": context,
    "shift_briefing": brief,
    "uc_function": f"{S}.generate_shift_brief",
    "uc_function_sample_output": fn_out,
}
dbutils.notebook.exit(json.dumps(result, default=str))
