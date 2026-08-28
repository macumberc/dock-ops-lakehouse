# Evidence · Stage 9 — Databricks App (FastAPI + React)

**What ran:** `app/` deployed as Databricks App **`dock-ops-app`** from the workspace path
`/Workspace/Users/chad.macumber@databricks.com/apps/dock-ops-app`.

- Deployment `01f1a325f7a81f1287e30d4296cae5a0` → **status SUCCEEDED**, message "App started successfully"
- App state: **RUNNING** · URL: `https://dock-ops-app-7474658947307895.aws.databricksapps.com`
- Service principal `b84c161c-7509-41e9-b779-68fb08f925be` granted: UC `SELECT`/`USE`/`EXECUTE`
  on the schema, warehouse `CAN_USE`, serving-endpoint `CAN_QUERY`, and a Lakebase Postgres
  role (`create-role`, SERVICE_PRINCIPAL / LAKEBASE_OAUTH_V1).

## Live deployed-app API responses (called with an OAuth bearer token)
```json
{
  "health":  {"status": "ok", "warehouse": "2a0649a9f0fb7773", "cv_endpoint": "dock-occupancy-cls"},
  "kpis":    {"detention_usd": "235799.0", "overtime_usd": "108780", "avg_util_pct": "40.2", "peak_util_pct": "94.8"},
  "docks":   {"source": "lakebase", "count": 36},
  "staffing":{"source": "lakebase", "count": 12}
}
```
`docks` and `staffing` report **`source: lakebase`** — the deployed service principal reads
the live board and staffing plan directly from **Lakebase Postgres**, exactly as designed
(the app falls back to the warehouse gold tables only if Postgres is unreachable).

## Deployed AI shift briefing (POST /api/briefing → Claude Sonnet 5, grounded)
```
Shift Briefing – Dock Ops
Situation: Network detention ($235.8K) and OT ($108.8K) remain elevated, driven by MEM's
severe 10–11am understaffing (gaps of 8–9 heads) despite low avg utilization (~40%)
network-wide — a scheduling mismatch, not a demand problem.
Top 3 Staffing Actions:
1. MEM, 10–11am, +9 headcount — Close the largest gap ...
```

## App server logs (all endpoints 200 OK, from the running app)
```
[APP] INFO: "GET /api/docks HTTP/1.1" 200 OK
[APP] INFO: "GET /api/staffing HTTP/1.1" 200 OK
[APP] INFO: "POST /api/briefing HTTP/1.1" 200 OK
[APP] INFO: "GET / HTTP/1.1" 200 OK
```

## What the app surfaces (React frontend, `app/static/index.html`)
- KPI header (detention, avoidable overtime, avg/peak utilization)
- **Live dock board** — 36 doors across 3 terminals, colored by real-time occupancy +
  CV-confirmed state (Lakebase)
- **Next-shift understaffing** table (forecast → Lakebase)
- **Utilization-by-hour** chart highlighting the mid-day crunch (warehouse)
- **AI shift briefing** panel (Claude Sonnet 5, grounded in the gold snapshot)

The app integrates all six stages: Lakeflow-ingested + UC-governed data, Lakebase serving,
the CV endpoint, the forecast, Genie's tables, and the GenAI briefing — in one console.
