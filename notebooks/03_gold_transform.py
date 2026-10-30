# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Gold transforms — utilization, terminal demand, current dock state
# MAGIC Meridian Freight Systems. Builds the governed analytics layer on top of
# MAGIC `silver_visits`:
# MAGIC - `gold_dock_utilization_hourly` — per door-hour occupancy & utilization %
# MAGIC - `gold_terminal_hourly` — per terminal-hour demand vs capacity + labor plan
# MAGIC   (the training table for the staffing-demand forecast)
# MAGIC - `gold_dock_current_state` — latest state per door (base for the live board)
# MAGIC
# MAGIC All tables are managed Unity Catalog tables in
# MAGIC `fedex_fevm_catalog.dock_ops_chad_macumber`.

# COMMAND ----------

import json
from pyspark.sql import functions as F

S = "fedex_fevm_catalog.dock_ops_chad_macumber"
spark.sql(f"USE {S}")

# Doors per terminal (business fact) + fixed labor plan constants.
TRAILERS_PER_WORKER_PER_HOUR = 1.6
BASE_HOURLY_LABOR = 28.0

# COMMAND ----------
# MAGIC %md ### Door-hour occupancy → `gold_dock_utilization_hourly`

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {S}.gold_dock_utilization_hourly
COMMENT 'Per dock-door, per-hour occupancy minutes and utilization %; a door is occupied from dock_assigned to gate_out.'
AS
WITH occ AS (
  SELECT visit_id, terminal, dock_id, dock_assigned AS occ_start, gate_out AS occ_end
  FROM {S}.silver_visits
  WHERE dock_assigned IS NOT NULL AND gate_out IS NOT NULL AND gate_out > dock_assigned
),
expanded AS (
  SELECT terminal, dock_id, visit_id, occ_start, occ_end,
    explode(sequence(date_trunc('HOUR', occ_start), date_trunc('HOUR', occ_end), INTERVAL 1 HOUR)) AS hour_ts
  FROM occ
),
perhour AS (
  SELECT terminal, dock_id, hour_ts,
    SUM(
      GREATEST(0.0,
        (unix_timestamp(LEAST(occ_end, hour_ts + INTERVAL 1 HOUR)) - unix_timestamp(GREATEST(occ_start, hour_ts)))
      ) / 60.0
    ) AS occupied_minutes_raw,
    COUNT(*) AS concurrent_visits
  FROM expanded
  GROUP BY terminal, dock_id, hour_ts
)
SELECT
  terminal, dock_id, hour_ts,
  hour(hour_ts) AS hour_of_day,
  dayofweek(hour_ts) AS day_of_week,
  ROUND(LEAST(occupied_minutes_raw, 60.0), 1) AS occupied_minutes,
  ROUND(occupied_minutes_raw, 1) AS demand_minutes,
  ROUND(LEAST(occupied_minutes_raw, 60.0) / 60.0 * 100, 1) AS utilization_pct,
  concurrent_visits
FROM perhour
""")
print("gold_dock_utilization_hourly:", spark.table(f"{S}.gold_dock_utilization_hourly").count())

# COMMAND ----------
# MAGIC %md ### Terminal-hour demand vs capacity + labor plan → `gold_terminal_hourly`

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {S}.gold_terminal_hourly
COMMENT 'Per terminal, per-hour trailer demand vs door capacity, active loads, scheduled vs recommended dock labor, and the labor gap. Training table for the staffing-demand forecast.'
AS
WITH doors AS (
  SELECT * FROM VALUES ('ATL',12),('DFW',10),('MEM',14) AS t(terminal, door_count)
),
-- active loads per terminal-hour (drives labor demand)
loads AS (
  SELECT terminal, load_start AS s, load_end AS e FROM {S}.silver_visits
  WHERE load_start IS NOT NULL AND load_end IS NOT NULL AND load_end > load_start
),
load_hours AS (
  SELECT terminal,
    explode(sequence(date_trunc('HOUR', s), date_trunc('HOUR', e), INTERVAL 1 HOUR)) AS hour_ts,
    s, e
  FROM loads
),
load_minutes AS (
  SELECT terminal, hour_ts,
    SUM(GREATEST(0.0,(unix_timestamp(LEAST(e, hour_ts + INTERVAL 1 HOUR)) - unix_timestamp(GREATEST(s, hour_ts)))/60.0)) AS load_minutes
  FROM load_hours GROUP BY terminal, hour_ts
),
-- door occupancy demand rolled up to terminal
occ AS (
  SELECT terminal, hour_ts, SUM(demand_minutes) AS demand_door_minutes, SUM(occupied_minutes) AS occupied_door_minutes
  FROM {S}.gold_dock_utilization_hourly GROUP BY terminal, hour_ts
),
-- arrivals + detention per terminal-hour
arr AS (
  SELECT terminal, date_trunc('HOUR', gate_in) AS hour_ts,
    COUNT(*) AS trailers_arrived,
    ROUND(AVG(wait_minutes),1) AS avg_wait_minutes,
    ROUND(SUM(detention_fee_usd),2) AS detention_fee_usd,
    SUM(CASE WHEN detention_hours > 0 THEN 1 ELSE 0 END) AS detained_trailers
  FROM {S}.silver_visits GROUP BY terminal, date_trunc('HOUR', gate_in)
),
-- Preserve arrival hours even when no door is occupied yet. Anchoring only
-- on occupancy drops gate-in detention fees for visits waiting for a door.
hour_spine AS (
  SELECT terminal, hour_ts FROM occ
  UNION
  SELECT terminal, hour_ts FROM arr
  UNION
  SELECT terminal, hour_ts FROM load_minutes
)
SELECT
  h.terminal, h.hour_ts,
  hour(h.hour_ts) AS hour_of_day,
  dayofweek(h.hour_ts) AS day_of_week,
  d.door_count,
  ROUND(COALESCE(o.occupied_door_minutes,0),1) AS occupied_door_minutes,
  ROUND(COALESCE(o.demand_door_minutes,0),1) AS demand_door_minutes,
  ROUND(COALESCE(o.occupied_door_minutes,0) / (d.door_count*60.0) * 100, 1) AS utilization_pct,
  ROUND(COALESCE(o.demand_door_minutes,0)  / (d.door_count*60.0) * 100, 1) AS demand_pct,
  COALESCE(a.trailers_arrived,0) AS trailers_arrived,
  COALESCE(a.avg_wait_minutes,0) AS avg_wait_minutes,
  COALESCE(a.detention_fee_usd,0) AS detention_fee_usd,
  COALESCE(a.detained_trailers,0) AS detained_trailers,
  ROUND(COALESCE(lm.load_minutes,0)/60.0,2) AS active_loader_hours,
  -- recommended dock labor for the hour (hindsight, from realized load-hours)
  CAST(CEIL(COALESCE(lm.load_minutes,0)/60.0 / {TRAILERS_PER_WORKER_PER_HOUR} * 1.6) AS INT) AS recommended_headcount,
  -- fixed shift plan (the status quo that misses the afternoon crunch)
  CAST(CASE
    WHEN hour(h.hour_ts) BETWEEN 6 AND 13 THEN ROUND(d.door_count*0.55)
    WHEN hour(h.hour_ts) BETWEEN 14 AND 21 THEN ROUND(d.door_count*0.55)
    ELSE ROUND(d.door_count*0.25) END AS INT) AS scheduled_headcount
FROM hour_spine h
JOIN doors d ON h.terminal = d.terminal
LEFT JOIN occ o ON h.terminal = o.terminal AND h.hour_ts = o.hour_ts
LEFT JOIN arr a ON h.terminal = a.terminal AND h.hour_ts = a.hour_ts
LEFT JOIN load_minutes lm ON h.terminal = lm.terminal AND h.hour_ts = lm.hour_ts
""")

# Add the labor gap + overtime cost columns.
spark.sql(f"""
CREATE OR REPLACE TABLE {S}.gold_terminal_hourly AS
SELECT *,
  (recommended_headcount - scheduled_headcount) AS labor_gap,
  ROUND(GREATEST(0, recommended_headcount - scheduled_headcount) * {BASE_HOURLY_LABOR} * 1.5, 2) AS overtime_cost_usd
FROM {S}.gold_terminal_hourly
""")
print("gold_terminal_hourly:", spark.table(f"{S}.gold_terminal_hourly").count())

# COMMAND ----------
# MAGIC %md ### Current dock state (base for the live operational board)

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {S}.gold_dock_current_state
COMMENT 'Latest known state per dock door as of the most recent telemetry; base for the Lakebase-served live operations board (augmented with CV predictions in stage 04).'
AS
WITH ref AS (SELECT MAX(gate_out) AS now_ts FROM {S}.silver_visits),
doors AS (
  SELECT concat(t.terminal,'-D', lpad(cast(d AS string),2,'0')) AS dock_id, t.terminal
  FROM VALUES ('ATL',12),('DFW',10),('MEM',14) AS t(terminal, n)
  LATERAL VIEW explode(sequence(1, t.n)) e AS d
),
active AS (
  SELECT v.dock_id, v.terminal, v.trailer_id, v.direction, v.dock_assigned, v.gate_out,
         ROW_NUMBER() OVER (PARTITION BY v.dock_id ORDER BY v.gate_out DESC) AS rn
  FROM {S}.silver_visits v, ref
  WHERE v.dock_assigned <= ref.now_ts AND v.gate_out >= ref.now_ts
),
last_visit AS (
  SELECT v.dock_id, MAX(v.gate_out) AS last_departed
  FROM {S}.silver_visits v GROUP BY v.dock_id
)
SELECT
  d.dock_id, d.terminal,
  (SELECT now_ts FROM ref) AS as_of_ts,
  CASE WHEN a.trailer_id IS NOT NULL THEN 'occupied' ELSE 'available' END AS telemetry_status,
  a.trailer_id AS current_trailer_id,
  a.direction AS current_direction,
  a.dock_assigned AS occupied_since,
  lv.last_departed
FROM doors d
LEFT JOIN active a ON d.dock_id = a.dock_id AND a.rn = 1
LEFT JOIN last_visit lv ON d.dock_id = lv.dock_id
""")
print("gold_dock_current_state:", spark.table(f"{S}.gold_dock_current_state").count())

# COMMAND ----------
# MAGIC %md ### Evidence summary

# COMMAND ----------

util = spark.table(f"{S}.gold_dock_utilization_hourly")
term = spark.table(f"{S}.gold_terminal_hourly")
state = spark.table(f"{S}.gold_dock_current_state")

# Peak-vs-trough utilization by hour of day (the mismatch story)
by_hour = (term.groupBy("hour_of_day")
           .agg(F.round(F.avg("utilization_pct"),1).alias("avg_util_pct"),
                F.round(F.avg("labor_gap"),2).alias("avg_labor_gap"))
           .orderBy("hour_of_day"))
by_hour.show(24)

result = {
  "gold_dock_utilization_hourly_rows": util.count(),
  "gold_terminal_hourly_rows": term.count(),
  "gold_dock_current_state_rows": state.count(),
  "docks_occupied_now": state.filter("telemetry_status='occupied'").count(),
  "total_detention_fee_usd": round(term.agg(F.sum("detention_fee_usd")).first()[0], 2),
  "total_overtime_cost_usd": round(term.agg(F.sum("overtime_cost_usd")).first()[0], 2),
  "peak_hour_avg_util_pct": by_hour.orderBy(F.desc("avg_util_pct")).first().asDict(),
}
print(json.dumps(result, indent=2, default=str))
dbutils.notebook.exit(json.dumps(result, default=str))
