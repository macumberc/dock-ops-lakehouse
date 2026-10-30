# Databricks notebook source
# MAGIC %md
# MAGIC # Meridian Freight: dock operations intelligence
# MAGIC
# MAGIC Meridian Freight is a fictional carrier with 36 loading doors across Atlanta,
# MAGIC Dallas, and Memphis. Arrival waves concentrate demand around midday while the
# MAGIC staffing plan stays flat. This synthetic scenario models $344,720 in detention
# MAGIC and overtime over 31 days, approximately $4.06 million at an annual run rate.
# MAGIC A supervisor can inspect dock conditions, review forecast staffing gaps, and
# MAGIC use an AI briefing to decide which action to approve.
# MAGIC
# MAGIC **All data is synthetic.** This walkthrough reads the demo's existing tables.
# MAGIC Historical dates and the forecast horizon remain visible. It does not change
# MAGIC staffing, deploy resources, or represent current Federal Express operations.
# MAGIC
# MAGIC [Operations console](https://dock-ops-app-7474658947307895.aws.databricksapps.com)
# MAGIC [Genie](https://fevm-fedex-fevm.cloud.databricks.com/genie/rooms/01f1a3243b00149fa4876211f8b5c004)
# MAGIC [Presentation](https://docs.google.com/presentation/d/1aHc3m1N-RoiVbmZy3XPoPNjJ76ItUt88AKvzdas3T2c/edit)

# COMMAND ----------

# Configure the current catalog and this presenter's isolated schema.
import json
import re
from datetime import datetime, timezone

principal = spark.sql("SELECT current_user()").first()[0]
username = re.sub(r"[^a-z0-9]+", "_", principal.split("@")[0].lower()).strip("_")
dbutils.widgets.text("catalog", spark.catalog.currentCatalog())
dbutils.widgets.text("schema_name", f"dock_ops_{username}")
catalog = dbutils.widgets.get("catalog")
schema_name = dbutils.widgets.get("schema_name")


def identifier(value: str) -> str:
    """Quote a single non-empty SQL identifier without allowing SQL injection."""
    if not value or "\x00" in value:
        raise ValueError("Select a non-empty catalog and schema in the notebook widgets.")
    return "`" + value.replace("`", "``") + "`"


def table(name: str) -> str:
    """Return a safely quoted three-part table name in the selected demo schema."""
    return ".".join(identifier(part) for part in (catalog, schema_name, name))


full_schema = f"{identifier(catalog)}.{identifier(schema_name)}"
required = {"silver_visits", "gold_terminal_hourly", "gold_dock_current_state",
            "gold_staffing_forecast", "gold_visit_fact"}
try:
    available = {row.tableName for row in spark.sql(f"SHOW TABLES IN {full_schema}").collect()}
except Exception as exc:
    raise RuntimeError(
        f"The demo schema {catalog}.{schema_name} is unavailable. Select the catalog "
        "containing your demo and run its setup job before presenting."
    ) from exc
missing = required - available
if missing:
    raise RuntimeError(f"Demo setup is incomplete in {catalog}.{schema_name}: "
                       f"missing {', '.join(sorted(missing))}. Run the setup workflow first.")
print(json.dumps({"verified_at_utc": datetime.now(timezone.utc).isoformat(),
                  "presenter": principal, "catalog": catalog, "schema_name": schema_name,
                  "tables_found": sorted(available), "data_classification": "synthetic"}, indent=2))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. The cost baseline and data dates
# MAGIC
# MAGIC **Tell:** The baseline quantifies the staffing decision.
# MAGIC **Show:** Compare the terminal costs and the actual simulation dates.
# MAGIC **Tell:** This is a modeled opportunity to investigate, with no realized savings claim.

# COMMAND ----------

# Show the simulation window and terminal-level economics.
display(spark.sql(f"""
WITH terminal_costs AS (
  SELECT terminal, MIN(hour_ts) AS history_start, MAX(hour_ts) AS history_end,
         ROUND(SUM(detention_fee_usd), 2) AS detention_usd,
         ROUND(SUM(overtime_cost_usd), 2) AS modeled_overtime_usd,
         ROUND(AVG(utilization_pct), 1) AS avg_utilization_pct,
         MAX(utilization_pct) AS peak_utilization_pct
  FROM {table('gold_terminal_hourly')}
  GROUP BY terminal
)
SELECT * FROM terminal_costs ORDER BY detention_usd DESC
"""))

# COMMAND ----------

# Reconcile gold detention against the independent visit-level source and
# recompute modeled overtime from staffing gaps rather than trusting a saved total.
reconciled = spark.sql(f"""
WITH visits AS (
  SELECT ROUND(SUM(detention_fee_usd), 2) AS visit_detention_usd,
         COUNT(*) AS trailer_visits
  FROM {table('silver_visits')}
), terminal_costs AS (
  SELECT ROUND(SUM(detention_fee_usd), 2) AS gold_detention_usd,
         ROUND(SUM(overtime_cost_usd), 2) AS modeled_overtime_usd,
         ROUND(SUM(GREATEST(0, recommended_headcount - scheduled_headcount) * 28 * 1.5), 2)
           AS recomputed_overtime_usd,
         DATEDIFF(MAX(DATE(hour_ts)), MIN(DATE(hour_ts))) + 1 AS calendar_days
  FROM {table('gold_terminal_hourly')}
)
SELECT *, ROUND(gold_detention_usd - visit_detention_usd, 2) AS detention_difference_usd,
       ROUND(modeled_overtime_usd - recomputed_overtime_usd, 2) AS overtime_difference_usd,
       ROUND((gold_detention_usd + modeled_overtime_usd) / calendar_days * 365, 2)
         AS illustrative_annual_cost_usd
FROM visits CROSS JOIN terminal_costs
""").first().asDict()
if abs(float(reconciled["detention_difference_usd"])) > 0.05:
    raise RuntimeError(f"Detention totals do not reconcile: {reconciled}. Stop and inspect the pipeline.")
if abs(float(reconciled["overtime_difference_usd"])) > 0.05:
    raise RuntimeError(f"Overtime totals do not reconcile: {reconciled}. Stop and inspect the formula.")
display(spark.createDataFrame([reconciled]))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. The hourly staffing mismatch
# MAGIC
# MAGIC **Tell:** A fixed staffing plan misses the midday arrival wave.
# MAGIC **Show:** Plot scheduled and recommended headcount by hour.
# MAGIC **Tell:** Use the gap to plan a shift, then validate practical staffing constraints.

# COMMAND ----------

# Show the hourly profile used by the presentation.
display(spark.sql(f"""
SELECT hour_of_day,
       ROUND(AVG(scheduled_headcount), 1) AS scheduled_workers,
       ROUND(AVG(recommended_headcount), 1) AS recommended_workers,
       ROUND(AVG(labor_gap), 1) AS labor_gap,
       ROUND(AVG(utilization_pct), 1) AS avg_utilization_pct
FROM {table('gold_terminal_hourly')}
GROUP BY hour_of_day ORDER BY hour_of_day
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Dock state and the forecast horizon
# MAGIC
# MAGIC **Tell:** Supervisors need the observation time and the next staffing decision.
# MAGIC **Show:** Inspect the 36-door snapshot and the highest predicted staffing gaps.
# MAGIC **Tell:** These timestamps describe a synthetic replay. Lakebase serves a copied
# MAGIC snapshot, so source freshness and sync freshness are separate checks.

# COMMAND ----------

# Display dock observations with the timestamp retained.
display(spark.sql(f"""
SELECT dock_id, terminal, as_of_ts, telemetry_status, current_trailer_id, cv_state
FROM {table('gold_dock_current_state')}
ORDER BY terminal, dock_id
"""))

# COMMAND ----------

# Discover the forecast's date column before presenting rows to handle schema drift.
forecast_columns = {field.name for field in spark.table(table("gold_staffing_forecast")).schema.fields}
forecast_date = next((name for name in ("forecast_hour_ts", "hour_ts", "forecast_date", "forecast_ts")
                      if name in forecast_columns), None)
if forecast_date is None:
    raise RuntimeError(f"Cannot identify the forecast timestamp in {sorted(forecast_columns)}. "
                       "Inspect the forecast table before presenting a date-relative claim.")
display(spark.sql(f"""
SELECT {identifier(forecast_date)} AS forecast_time, terminal, hour_of_day,
       forecast_headcount, scheduled_headcount, labor_gap, projected_overtime_cost_usd
FROM {table('gold_staffing_forecast')}
WHERE understaffed AND day_of_week NOT IN (1, 7)
ORDER BY labor_gap DESC, forecast_time, terminal LIMIT 15
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. An evidence-backed leadership answer
# MAGIC
# MAGIC Open the linked Genie space and ask: **Which terminal has the highest total
# MAGIC detention fees?** Inspect the generated SQL. The query below gives the
# MAGIC expected result directly from gold so the answer can be checked.
# MAGIC
# MAGIC Then open the app and generate a shift briefing. Compare its staffing action
# MAGIC against the forecast rows. Review any dollar-impact claim before using it.

# COMMAND ----------

# Verify the answer to the leadership question directly from source rows.
display(spark.sql(f"""
WITH terminal_fees AS (
  SELECT terminal, ROUND(SUM(detention_fee_usd), 0) AS detention_usd
  FROM {table('gold_terminal_hourly')} GROUP BY terminal
)
SELECT * FROM terminal_fees ORDER BY detention_usd DESC
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Governance for the architect
# MAGIC
# MAGIC Worker identifiers use a table column mask controlled by group membership.
# MAGIC This is distinct from a governed-tag ABAC policy. Unity Catalog controls apply
# MAGIC to lakehouse reads. The Lakebase copy uses its own Postgres roles and grants.
# MAGIC Inspect the app service principal and the configured Genie identity separately.

# COMMAND ----------

# Display masked identifiers under the presenter's identity and the table's grants.
display(spark.sql(f"SELECT DISTINCT worker_id FROM {table('gold_visit_fact')} LIMIT 5"))
display(spark.sql(f"SHOW GRANTS ON TABLE {table('gold_visit_fact')}"))
display(spark.sql(f"DESCRIBE TABLE EXTENDED {table('gold_visit_fact')}"))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Pilot decision and teardown
# MAGIC
# MAGIC Propose Memphis as the first terminal. Agree an operations sponsor, supervisor,
# MAGIC platform owner, and baseline period. Run recommendations in shadow mode before
# MAGIC trialing supervisor-approved staffing changes. Measure detention per trailer,
# MAGIC overtime per handled trailer, model error, and data freshness against matched shifts.
# MAGIC
# MAGIC Use the package and `scripts/teardown.sh` for deliberate teardown. Do not run
# MAGIC cleanup during the presentation. Schema deletion cascades to all demo data and
# MAGIC models. App, endpoint, Genie, Lakebase, pipeline, and workspace launcher resources
# MAGIC require explicit cleanup outside the schema.

# COMMAND ----------

# Return machine-readable evidence when the notebook runs as a validation job.
dbutils.notebook.exit(json.dumps({"status": "validated", "data_classification": "synthetic",
                                "catalog": catalog, "schema_name": schema_name,
                                "reconciliation": reconciled}, default=str))
