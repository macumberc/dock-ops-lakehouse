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

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

CATALOG = "fedex_fevm_catalog"
SCHEMA = "dock_ops_chad_macumber"
FQ = f"{CATALOG}.{SCHEMA}"
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "2a0649a9f0fb7773")
CV_ENDPOINT = os.getenv("SERVING_ENDPOINT", "dock-occupancy-cls")
GENAI_ENDPOINT = "databricks-claude-sonnet-5"
LAKEBASE_HOST = os.getenv("PGHOST", "ep-square-resonance-d8lt69ul.database.us-east-2.cloud.databricks.com")
LAKEBASE_ENDPOINT = os.getenv(
    "LAKEBASE_ENDPOINT", "projects/dock-ops/branches/production/endpoints/primary"
)
LAKEBASE_DB = os.getenv("PGDATABASE", "databricks_postgres")

_profile = os.getenv("DBX_PROFILE")
w = WorkspaceClient(profile=_profile) if _profile else WorkspaceClient()

app = FastAPI(title="Meridian Dock Operations Console")


# --- data access helpers ------------------------------------------------------
def sql_rows(statement: str) -> tuple[list[str], list[list]]:
    """Run SQL on the serverless warehouse via the SDK statement API."""
    from databricks.sdk.service.sql import StatementState

    r = w.statement_execution.execute_statement(
        statement=statement, warehouse_id=WAREHOUSE_ID, wait_timeout="50s"
    )
    while r.status and r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        r = w.statement_execution.get_statement(r.statement_id)
    cols = [c.name for c in r.manifest.schema.columns] if r.manifest else []
    data = r.result.data_array if (r.result and r.result.data_array) else []
    return cols, data


def dicts(cols: list[str], rows: list[list]) -> list[dict]:
    return [dict(zip(cols, r)) for r in rows]


def lakebase_query(sql: str) -> list[dict]:
    """Query the Lakebase Postgres operational store (OAuth token, SSL)."""
    import psycopg2

    token = w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token
    user = w.current_user.me().user_name
    conn = psycopg2.connect(host=LAKEBASE_HOST, port=5432, dbname=LAKEBASE_DB,
                            user=user, password=token, sslmode="require")
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
    return {"status": "ok", "warehouse": WAREHOUSE_ID, "cv_endpoint": CV_ENDPOINT}


@app.get("/api/kpis")
def kpis() -> Any:
    cols, rows = sql_rows(f"""
      SELECT ROUND(SUM(detention_fee_usd),0) AS detention_usd,
             ROUND(SUM(overtime_cost_usd),0) AS overtime_usd,
             ROUND(AVG(utilization_pct),1) AS avg_util_pct,
             MAX(utilization_pct) AS peak_util_pct
      FROM {FQ}.gold_terminal_hourly
    """)
    totals = dicts(cols, rows)[0] if rows else {}
    tcols, trows = sql_rows(f"""
      SELECT terminal, ROUND(SUM(detention_fee_usd),0) AS detention_usd,
             ROUND(SUM(overtime_cost_usd),0) AS overtime_usd,
             ROUND(AVG(utilization_pct),1) AS avg_util_pct, MAX(utilization_pct) AS peak_util_pct
      FROM {FQ}.gold_terminal_hourly GROUP BY terminal ORDER BY terminal
    """)
    return {"totals": totals, "by_terminal": dicts(tcols, trows)}


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
    """Live dock board from Lakebase; falls back to the gold table if PG is unreachable."""
    q = ("SELECT dock_id, terminal, telemetry_status, current_trailer_id, cv_state "
         "FROM dock_ops.dock_current_state ORDER BY dock_id")
    try:
        return {"source": "lakebase", "docks": lakebase_query(q)}
    except Exception as e:  # pragma: no cover - resilience path
        cols, rows = sql_rows(
            f"SELECT dock_id, terminal, telemetry_status, current_trailer_id, cv_state "
            f"FROM {FQ}.gold_dock_current_state ORDER BY dock_id")
        return {"source": "warehouse_fallback", "error": str(e)[:200], "docks": dicts(cols, rows)}


@app.get("/api/staffing")
def staffing() -> Any:
    """Next-shift understaffing plan from Lakebase; falls back to the gold table."""
    q = ("SELECT terminal, hour_of_day, forecast_headcount, scheduled_headcount, labor_gap, "
         "projected_overtime_cost_usd FROM dock_ops.staffing_forecast "
         "WHERE understaffed AND day_of_week NOT IN (1,7) ORDER BY labor_gap DESC LIMIT 12")
    try:
        return {"source": "lakebase", "rows": lakebase_query(q)}
    except Exception as e:  # pragma: no cover
        cols, rows = sql_rows(
            f"SELECT terminal, hour_of_day, forecast_headcount, scheduled_headcount, labor_gap, "
            f"projected_overtime_cost_usd FROM {FQ}.gold_staffing_forecast "
            f"WHERE understaffed AND day_of_week NOT IN (1,7) ORDER BY labor_gap DESC LIMIT 12")
        return {"source": "warehouse_fallback", "error": str(e)[:200], "rows": dicts(cols, rows)}


@app.post("/api/briefing")
def briefing() -> Any:
    """Generate a grounded AI shift briefing from the current gold snapshot."""
    k = kpis()
    s = staffing()
    context = {
        "kpis": k["totals"],
        "by_terminal": k["by_terminal"],
        "top_understaffed": s.get("rows", [])[:6],
    }
    prompt = (
        "You are a dock operations advisor for Meridian Freight Systems. From the JSON "
        "snapshot, write a concise shift briefing: a one-line situation summary and the "
        "top 3 prioritized staffing actions (terminal, hour, headcount move) with projected "
        "impact on detention and overtime. Under 180 words.\n\n" + str(context)
    )
    resp = w.serving_endpoints.query(
        name=GENAI_ENDPOINT,
        messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)],
        max_tokens=500,
    )
    return {"briefing": resp.choices[0].message.content, "context": context}


# --- static frontend ----------------------------------------------------------
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")


@app.get("/api")
def api_index() -> JSONResponse:
    return JSONResponse({"endpoints": ["/api/health", "/api/kpis", "/api/utilization",
                                       "/api/docks", "/api/staffing", "/api/briefing"]})
