"""Meridian Freight — Dock Operations Console (Databricks App backend).

FastAPI backend that surfaces the dock-ops lakehouse to supervisors:
  - live dock board + next-shift staffing plan  ->  Lakebase Postgres (operational)
  - KPIs + hourly utilization/labor profile     ->  SQL warehouse (analytics)
  - dock-camera classification                  ->  CV serving endpoint
  - AI shift briefing                           ->  Foundation Model (Claude)

All auth flows through the Databricks SDK: in the Apps runtime the service principal
credentials are injected automatically; locally set DBX_PROFILE=fedex-fevm.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from model_output import output_text

CATALOG = os.environ["DATABRICKS_CATALOG"]
SCHEMA = os.environ["DATABRICKS_SCHEMA"]
FQ = ".".join("`" + part.replace("`", "``") + "`" for part in (CATALOG, SCHEMA))
WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
GENAI_ENDPOINT = os.getenv("GENAI_ENDPOINT", "databricks-claude-sonnet-5")
LAKEBASE_HOST = os.getenv("PGHOST", "ep-square-resonance-d8lt69ul.database.us-east-2.cloud.databricks.com")
LAKEBASE_ENDPOINT = os.getenv(
    "LAKEBASE_ENDPOINT", "projects/dock-ops/branches/production/endpoints/primary"
)
LAKEBASE_DB = os.getenv("PGDATABASE", "databricks_postgres")

_profile = os.getenv("DBX_PROFILE")
# Apps inject OAuth client credentials; an inherited PAT must not override them.
_conflicting_token = os.environ.pop("DATABRICKS_TOKEN", None)
try:
    w = WorkspaceClient(profile=_profile) if _profile else WorkspaceClient()
finally:
    if _conflicting_token is not None:
        os.environ["DATABRICKS_TOKEN"] = _conflicting_token
logger = logging.getLogger(__name__)

app = FastAPI(title="Meridian Dock Operations Console")


# --- data access helpers ------------------------------------------------------
def sql_rows(statement: str) -> tuple[list[str], list[list]]:
    """Run SQL on the serverless warehouse via the SDK statement API."""
    from databricks.sdk.service.sql import StatementState

    r = w.statement_execution.execute_statement(
        statement=statement, warehouse_id=WAREHOUSE_ID, wait_timeout="50s"
    )
    deadline = time.monotonic() + 120
    while r.status and r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() >= deadline:
            raise HTTPException(504, "The analytics query timed out. Check the SQL warehouse and retry.")
        time.sleep(0.5)
        r = w.statement_execution.get_statement(r.statement_id)
    if not r.status or r.status.state != StatementState.SUCCEEDED:
        logger.error("Warehouse statement %s failed: %s", r.statement_id, r.status)
        raise HTTPException(503, "The analytics query failed. Check the warehouse and demo-table access.")
    cols = [c.name for c in r.manifest.schema.columns] if r.manifest else []
    data = r.result.data_array if (r.result and r.result.data_array) else []
    return cols, data


def dicts(cols: list[str], rows: list[list]) -> list[dict]:
    """Map query rows to their column names."""
    return [dict(zip(cols, r)) for r in rows]


def lakebase_query(sql: str) -> list[dict]:
    """Query the Lakebase Postgres operational store (OAuth token, SSL)."""
    import psycopg2

    token = w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token
    user = w.current_user.me().user_name
    conn = psycopg2.connect(host=LAKEBASE_HOST, port=5432, dbname=LAKEBASE_DB,
                            user=user, password=token, sslmode="require", connect_timeout=10)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


# --- API ----------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "warehouse_configured": bool(WAREHOUSE_ID)}


@app.get("/api/kpis")
def kpis() -> Any:
    cols, rows = sql_rows(f"""
      SELECT ROUND(SUM(detention_fee_usd),0) AS detention_usd,
             ROUND(SUM(overtime_cost_usd),0) AS overtime_usd,
             ROUND(AVG(utilization_pct),1) AS avg_util_pct,
             MAX(utilization_pct) AS peak_util_pct,
             MIN(hour_ts) AS period_start,
             MAX(hour_ts) AS period_end
      FROM {FQ}.gold_terminal_hourly
    """)
    totals = dicts(cols, rows)[0] if rows else {}
    tcols, trows = sql_rows(f"""
      SELECT terminal, ROUND(SUM(detention_fee_usd),0) AS detention_usd,
             ROUND(SUM(overtime_cost_usd),0) AS overtime_usd,
             ROUND(AVG(utilization_pct),1) AS avg_util_pct, MAX(utilization_pct) AS peak_util_pct
      FROM {FQ}.gold_terminal_hourly GROUP BY terminal ORDER BY terminal
    """)
    return {
        "source": f"{FQ}.gold_terminal_hourly",
        "snapshot_type": "synthetic_historical_replay",
        "totals": totals,
        "by_terminal": dicts(tcols, trows),
    }


@app.get("/api/utilization")
def utilization() -> Any:
    cols, rows = sql_rows(f"""
      SELECT hour_of_day,
             ROUND(AVG(utilization_pct),1) AS avg_util_pct,
             ROUND(AVG(scheduled_headcount),1) AS scheduled,
             ROUND(AVG(recommended_headcount),1) AS recommended,
             ROUND(AVG(labor_gap),1) AS labor_gap
      FROM {FQ}.gold_terminal_hourly GROUP BY hour_of_day ORDER BY hour_of_day
    """)
    return dicts(cols, rows)


@app.get("/api/docks")
def docks() -> Any:
    """Historical dock snapshot from Lakebase, with a warehouse resilience path."""
    q = ("SELECT dock_id, terminal, as_of_ts, telemetry_status, current_trailer_id, cv_state "
         "FROM dock_ops.dock_current_state ORDER BY dock_id")
    try:
        rows = lakebase_query(q)
        return {
            "source": "Lakebase: dock_ops.dock_current_state",
            "snapshot_type": "synthetic_historical_replay",
            "snapshot_as_of": max((r.get("as_of_ts") for r in rows), default=None),
            "docks": rows,
        }
    except Exception as e:  # pragma: no cover - resilience path
        logger.warning("Lakebase dock read unavailable (%s); using gold snapshot", type(e).__name__)
        cols, rows = sql_rows(
            f"SELECT dock_id, terminal, as_of_ts, telemetry_status, current_trailer_id, cv_state "
            f"FROM {FQ}.gold_dock_current_state ORDER BY dock_id")
        result = dicts(cols, rows)
        return {
            "source": f"SQL warehouse fallback: {FQ}.gold_dock_current_state",
            "snapshot_type": "synthetic_historical_replay",
            "snapshot_as_of": max((r.get("as_of_ts") for r in result), default=None),
            "source_notice": "Lakebase was unavailable; showing the matching gold snapshot.",
            "docks": result,
        }


@app.get("/api/staffing")
def staffing() -> Any:
    """Historical forecast window from Lakebase, with a warehouse resilience path."""
    q = ("SELECT terminal, hour_ts, hour_of_day, forecast_headcount, scheduled_headcount, labor_gap, "
         "projected_overtime_cost_usd FROM dock_ops.staffing_forecast "
         "WHERE understaffed AND day_of_week NOT IN (1,7) ORDER BY labor_gap DESC, hour_ts, terminal LIMIT 12")
    try:
        rows = lakebase_query(q)
        return {
            "source": "Lakebase: dock_ops.staffing_forecast",
            "snapshot_type": "synthetic_historical_forecast",
            "forecast_start": min((r.get("hour_ts") for r in rows), default=None),
            "forecast_end": max((r.get("hour_ts") for r in rows), default=None),
            "rows": rows,
        }
    except Exception as e:  # pragma: no cover
        logger.warning("Lakebase staffing read unavailable (%s); using gold forecast", type(e).__name__)
        cols, rows = sql_rows(
            f"SELECT terminal, hour_ts, hour_of_day, forecast_headcount, scheduled_headcount, labor_gap, "
            f"projected_overtime_cost_usd FROM {FQ}.gold_staffing_forecast "
            f"WHERE understaffed AND day_of_week NOT IN (1,7) ORDER BY labor_gap DESC, hour_ts, terminal LIMIT 12")
        result = dicts(cols, rows)
        return {
            "source": f"SQL warehouse fallback: {FQ}.gold_staffing_forecast",
            "snapshot_type": "synthetic_historical_forecast",
            "forecast_start": min((r.get("hour_ts") for r in result), default=None),
            "forecast_end": max((r.get("hour_ts") for r in result), default=None),
            "source_notice": "Lakebase was unavailable; showing the matching gold forecast.",
            "rows": result,
        }


@app.post("/api/briefing")
def briefing() -> Any:
    """Generate a grounded AI shift briefing from the current gold snapshot."""
    k = kpis()
    s = staffing()
    safe_kpis = {
        key: value for key, value in k["totals"].items()
        if key in {"overtime_usd", "avg_util_pct", "peak_util_pct", "period_start", "period_end"}
    }
    safe_terminals = [
        {key: value for key, value in row.items() if key != "detention_usd"}
        for row in k["by_terminal"]
    ]
    context = {
        "data_status": "Synthetic historical replay; not current operations.",
        "kpi_source": k["source"],
        "kpis": safe_kpis,
        "by_terminal": safe_terminals,
        "staffing_source": s.get("source"),
        "forecast_window": [s.get("forecast_start"), s.get("forecast_end")],
        "top_understaffed": s.get("rows", [])[:3],
    }
    prompt = (
        "Summarize these fictional warehouse staffing records for a supervisor at Meridian Freight. "
        "All records are synthetic historical simulations. Give up to three staffing recommendations, "
        "citing each shift's date, terminal, scheduled workers, required workers, and additional workers "
        "needed. projected_overtime_cost_usd is a modeled hourly labor cost, not demonstrated savings. "
        "Use only the records below, keep the briefing under 180 words, and require supervisor review.\n\n"
        + json.dumps(context["top_understaffed"], default=str)
    )
    try:
        resp = w.serving_endpoints.query(
            name=GENAI_ENDPOINT,
            messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)],
            max_tokens=500,
        )
    except DatabricksError as exc:
        logger.warning("Briefing request failed (%s)", type(exc).__name__)
        raise HTTPException(503, "The AI service could not generate this briefing. Review the staffing table directly.") from exc
    content = resp.choices[0].message.content if resp.choices and resp.choices[0].message else None
    text = output_text(content)
    if not text:
        raise HTTPException(503, "The AI service returned no briefing. Review the staffing table directly.")
    return {
        "briefing": text,
        "model": GENAI_ENDPOINT,
        "disclaimer": "AI-generated from a synthetic historical snapshot; verify before use.",
        "context": context,
    }


# --- static frontend ----------------------------------------------------------
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")


@app.get("/api")
def api_index() -> JSONResponse:
    return JSONResponse({"endpoints": ["/api/health", "/api/kpis", "/api/utilization",
                                       "/api/docks", "/api/staffing", "/api/briefing"]})
