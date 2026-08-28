# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Unity Catalog governance
# MAGIC Meridian Freight Systems. Governance across the dock-ops objects: a governed
# MAGIC managed **visit-fact** table, column comments, classification **tags**, a
# MAGIC **column mask** on the sensitive worker-id, role-based **grants** on the curated
# MAGIC gold layer, and a **lineage** check. Everything lives in
# MAGIC `fedex_fevm_catalog.dock_ops_chad_macumber`.
# MAGIC
# MAGIC NOTE: the silver objects are DLT materialized views; column masks and column-level
# MAGIC ALTERs require a managed **table**, so worker-level detail is materialized into
# MAGIC `gold_visit_fact` and governed there. Applying UC tags requires `APPLY TAG`;
# MAGIC governed tags additionally require `ASSIGN` on the tag.

# COMMAND ----------

import json
S = "fedex_fevm_catalog.dock_ops_chad_macumber"
spark.sql(f"USE {S}")
log = {}

# COMMAND ----------
# MAGIC %md ### Governed managed visit-fact table (carries the sensitive worker id)

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {S}.gold_visit_fact
COMMENT 'Curated visit-level fact table for detailed dock analysis. Managed UC table; worker_id is masked.'
AS SELECT
  visit_id, terminal, terminal_name, dock_id, trailer_id, direction, freight_weight_lbs,
  worker_id, gate_in, dock_assigned, load_start, load_end, gate_out,
  wait_minutes, load_minutes, dwell_minutes, detention_hours, detention_fee_usd, visit_date
FROM {S}.silver_visits
""")
print("gold_visit_fact rows:", spark.table(f"{S}.gold_visit_fact").count())

# COMMAND ----------
# MAGIC %md ### Column comments (documentation)

# COMMAND ----------

for stmt in [
    f"ALTER TABLE {S}.gold_visit_fact ALTER COLUMN wait_minutes COMMENT 'Minutes from gate-in to dock assignment; the driver of trailer detention.'",
    f"ALTER TABLE {S}.gold_visit_fact ALTER COLUMN detention_fee_usd COMMENT 'Detention charge accrued past the free window (USD).'",
    f"ALTER TABLE {S}.gold_visit_fact ALTER COLUMN worker_id COMMENT 'Dock worker who performed the load. Sensitive — protected by a column mask.'",
    f"ALTER TABLE {S}.gold_terminal_hourly ALTER COLUMN labor_gap COMMENT 'Recommended minus scheduled dock headcount for the hour; positive = understaffed.'",
]:
    spark.sql(stmt)
print("column comments applied")

# COMMAND ----------
# MAGIC %md ### Classification tags (data domain + sensitivity)

# COMMAND ----------

# NOTE: this workspace enforces governed tag policies (e.g. key `data_domain`
# only permits value `train`; key `pii` only permits `ssn`/`address`). worker_id
# is an internal id, not SSN/address, so we use free-form tag keys and respect the
# governed keys rather than mislabel the column — a governance signal in itself.
tag_stmts = [
    f"ALTER SCHEMA {S} SET TAGS ('mfs_project' = 'fe_bar_dock_ops')",
    f"ALTER SCHEMA {S} SET TAGS ('mfs_data_class' = 'synthetic')",
    f"ALTER SCHEMA {S} SET TAGS ('mfs_domain' = 'logistics')",
    f"ALTER TABLE {S}.gold_visit_fact SET TAGS ('layer' = 'gold', 'contains_worker_id' = 'true')",
    f"ALTER TABLE {S}.gold_terminal_hourly SET TAGS ('layer' = 'gold', 'business_ready' = 'true')",
    f"ALTER TABLE {S}.gold_dock_current_state SET TAGS ('layer' = 'gold', 'serving' = 'lakebase')",
    f"ALTER TABLE {S}.gold_visit_fact ALTER COLUMN worker_id SET TAGS ('mfs_sensitivity' = 'confidential')",
]
applied, failed = [], []
for s in tag_stmts:
    try:
        spark.sql(s); applied.append(s.split("SET TAGS")[0].strip()[:90])
    except Exception as e:
        failed.append(f"{s[:60]}... -> {str(e)[:120]}")
log["tags_applied"] = applied
log["tags_failed"] = failed
print("tags applied:", len(applied), "failed:", len(failed))
for f in failed: print("  FAIL:", f)

# COMMAND ----------
# MAGIC %md ### Column mask on the sensitive worker-id (ABAC — references group membership)

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {S}.mask_worker_id(worker STRING)
RETURN CASE WHEN is_account_group_member('dock_supervisors') THEN worker ELSE 'W-REDACTED' END
""")
spark.sql(f"ALTER TABLE {S}.gold_visit_fact ALTER COLUMN worker_id SET MASK {S}.mask_worker_id")
print("column mask created + applied on gold_visit_fact.worker_id")

masked = spark.sql(f"SELECT DISTINCT worker_id FROM {S}.gold_visit_fact LIMIT 5").collect()
log["worker_id_values_seen"] = [r.worker_id for r in masked]
print("worker_id as seen by this (non-supervisor) principal:", log["worker_id_values_seen"])

# COMMAND ----------
# MAGIC %md ### Role-based grants — analysts get the curated gold layer only

# COMMAND ----------

grant_stmts = [
    f"GRANT SELECT ON TABLE {S}.gold_terminal_hourly TO `account users`",
    f"GRANT SELECT ON TABLE {S}.gold_dock_utilization_hourly TO `account users`",
    f"GRANT SELECT ON TABLE {S}.gold_dock_current_state TO `account users`",
    f"GRANT SELECT ON TABLE {S}.gold_staffing_forecast TO `account users`",
    f"GRANT SELECT ON TABLE {S}.gold_dock_image_scored TO `account users`",
]
granted, gfailed = [], []
for s in grant_stmts:
    try:
        spark.sql(s); granted.append(s)
    except Exception as e:
        gfailed.append(f"{s[:60]}... -> {str(e)[:120]}")
log["grants_applied"] = len(granted)
log["grants_failed"] = gfailed
print("grants applied:", len(granted), "failed:", len(gfailed))

grants = spark.sql(f"SHOW GRANTS ON TABLE {S}.gold_dock_current_state").collect()
log["grants_on_current_state"] = [f"{r.Principal}:{r.ActionType}" for r in grants][:20]
print("grants on gold_dock_current_state:", log["grants_on_current_state"])

# COMMAND ----------
# MAGIC %md ### Lineage — the gold serving table traces back to the raw ingest

# COMMAND ----------

try:
    lin = spark.sql(f"""
        SELECT source_table_full_name, target_table_full_name
        FROM system.access.table_lineage
        WHERE target_table_schema = 'dock_ops_chad_macumber'
          AND source_table_full_name IS NOT NULL
        GROUP BY source_table_full_name, target_table_full_name
        ORDER BY target_table_full_name
        LIMIT 30
    """).collect()
    log["lineage_edges"] = [f"{r.source_table_full_name} -> {r.target_table_full_name}" for r in lin]
    print("lineage edges captured:", len(log["lineage_edges"]))
    for e in log["lineage_edges"]:
        print("  ", e)
except Exception as e:
    log["lineage_error"] = str(e)[:200]
    print("lineage query note:", str(e)[:200])

# COMMAND ----------
# MAGIC %md ### Object inventory

# COMMAND ----------

tables = spark.sql(f"SHOW TABLES IN {S}").collect()
log["tables_in_schema"] = [r.tableName for r in tables]
funcs = spark.sql(f"SHOW USER FUNCTIONS IN {S}").collect()
log["functions_in_schema"] = [r.function for r in funcs]
print("tables:", log["tables_in_schema"])
print("functions:", log["functions_in_schema"])

dbutils.notebook.exit(json.dumps(log, default=str))
