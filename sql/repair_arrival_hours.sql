-- Repair the original synthetic demo's omitted gate-in hours without replacing
-- existing data or removing the dock snapshot's CV columns. Idempotent.
MERGE INTO fedex_fevm_catalog.dock_ops_chad_macumber.gold_terminal_hourly AS target
USING (
  WITH arrivals AS (
    SELECT terminal, date_trunc('HOUR', gate_in) AS hour_ts,
           COUNT(*) AS trailers_arrived,
           ROUND(AVG(wait_minutes), 1) AS avg_wait_minutes,
           ROUND(SUM(detention_fee_usd), 2) AS detention_fee_usd,
           SUM(CASE WHEN detention_hours > 0 THEN 1 ELSE 0 END) AS detained_trailers
    FROM fedex_fevm_catalog.dock_ops_chad_macumber.silver_visits
    GROUP BY terminal, date_trunc('HOUR', gate_in)
  ), missing AS (
    SELECT a.*
    FROM arrivals a
    LEFT ANTI JOIN fedex_fevm_catalog.dock_ops_chad_macumber.gold_terminal_hourly g
      ON a.terminal = g.terminal AND a.hour_ts = g.hour_ts
  ), doors AS (
    SELECT * FROM VALUES ('ATL', 12), ('DFW', 10), ('MEM', 14) AS d(terminal, door_count)
  ), labor AS (
    SELECT m.*, d.door_count,
           CAST(ROUND(d.door_count * CASE WHEN hour(m.hour_ts) BETWEEN 6 AND 21
                                         THEN 0.55 ELSE 0.25 END) AS INT) AS scheduled_headcount
    FROM missing m JOIN doors d ON m.terminal = d.terminal
  )
  SELECT terminal, hour_ts, hour(hour_ts) AS hour_of_day, dayofweek(hour_ts) AS day_of_week,
         door_count, 0 AS occupied_door_minutes, 0 AS demand_door_minutes,
         0 AS utilization_pct, 0 AS demand_pct, trailers_arrived, avg_wait_minutes,
         detention_fee_usd, detained_trailers, 0 AS active_loader_hours,
         0 AS recommended_headcount, scheduled_headcount,
         -scheduled_headcount AS labor_gap, 0 AS overtime_cost_usd
  FROM labor
) AS source
ON target.terminal = source.terminal AND target.hour_ts = source.hour_ts
WHEN NOT MATCHED THEN INSERT *
