#!/usr/bin/env python3
"""Load the operational gold tables into Lakebase Postgres for low-latency serving.

Reads the curated gold state from the SQL warehouse and writes it into the Lakebase
Autoscaling Postgres endpoint (the store the app reads live). Run locally with the
`fedex-fevm` profile. Idempotent: recreates the served tables each run.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from dbsql import run  # noqa: E402
from dock_ops import config, lakebase  # noqa: E402

USER = "chad.macumber@databricks.com"
S = config.full_schema()
PG = config.LAKEBASE_PG_SCHEMA

CURRENT_STATE_COLS = [
    "dock_id", "terminal", "telemetry_status", "current_trailer_id", "current_direction",
    "occupied_since", "last_departed", "cv_state", "cv_frame_ts", "as_of_ts",
]
FORECAST_COLS = [
    "terminal", "hour_ts", "hour_of_day", "day_of_week", "forecast_headcount",
    "scheduled_headcount", "labor_gap", "projected_overtime_cost_usd", "understaffed",
]


def main() -> None:
    token = lakebase.token_via_cli()
    conn = lakebase.connect(token=token, user=USER)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {PG}")

    # --- live dock board -----------------------------------------------------
    cur.execute(f"DROP TABLE IF EXISTS {PG}.dock_current_state")
    cur.execute(f"""
      CREATE TABLE {PG}.dock_current_state (
        dock_id text PRIMARY KEY, terminal text, telemetry_status text,
        current_trailer_id text, current_direction text,
        occupied_since timestamptz, last_departed timestamptz,
        cv_state text, cv_frame_ts timestamptz, as_of_ts timestamptz)
    """)
    _, rows = run(f"SELECT {', '.join(CURRENT_STATE_COLS)} FROM {S}.gold_dock_current_state")
    ph = ",".join(["%s"] * len(CURRENT_STATE_COLS))
    cur.executemany(f"INSERT INTO {PG}.dock_current_state VALUES ({ph})", rows)

    # --- next-shift staffing plan -------------------------------------------
    cur.execute(f"DROP TABLE IF EXISTS {PG}.staffing_forecast")
    cur.execute(f"""
      CREATE TABLE {PG}.staffing_forecast (
        terminal text, hour_ts timestamptz, hour_of_day int, day_of_week int,
        forecast_headcount int, scheduled_headcount int, labor_gap int,
        projected_overtime_cost_usd numeric, understaffed boolean)
    """)
    _, frows = run(f"SELECT {', '.join(FORECAST_COLS)} FROM {S}.gold_staffing_forecast")
    ph = ",".join(["%s"] * len(FORECAST_COLS))
    cur.executemany(f"INSERT INTO {PG}.staffing_forecast VALUES ({ph})", frows)

    # index for the app's per-terminal reads
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_sf_terminal ON {PG}.staffing_forecast(terminal, hour_ts)")

    # --- verify (read back from Postgres) -----------------------------------
    cur.execute(f"SELECT count(*) FROM {PG}.dock_current_state")
    n_state = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM {PG}.staffing_forecast")
    n_fc = cur.fetchone()[0]
    cur.execute(f"""SELECT terminal, telemetry_status, cv_state, count(*)
                    FROM {PG}.dock_current_state GROUP BY 1,2,3 ORDER BY 1,2""")
    sample_state = cur.fetchall()
    cur.execute(f"""SELECT terminal, hour_of_day, forecast_headcount, scheduled_headcount, labor_gap
                    FROM {PG}.staffing_forecast WHERE understaffed AND day_of_week NOT IN (1,7)
                    ORDER BY labor_gap DESC LIMIT 6""")
    sample_fc = cur.fetchall()
    conn.close()

    evidence = {
        "lakebase_host": config.LAKEBASE_HOST,
        "pg_version": "PostgreSQL 17.11",
        "schema": PG,
        "dock_current_state_rows": n_state,
        "staffing_forecast_rows": n_fc,
        "state_breakdown_from_postgres": sample_state,
        "top_understaffed_from_postgres": sample_fc,
    }
    print(json.dumps(evidence, indent=2, default=str))
    with open("evidence/08_lakebase.json", "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    print("\nLakebase sync complete — served tables live in Postgres.")


if __name__ == "__main__":
    main()
