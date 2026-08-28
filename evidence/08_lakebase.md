# Evidence · Stage 7 — Lakebase operational serving

**What ran:** `scripts/lakebase_sync.py` — provisions/loads the Lakebase Autoscaling
Postgres store the app reads live, then reads the tables back **from Postgres** to prove
serving.

## Lakebase infrastructure provisioned (Autoscaling Postgres)
Created via the `databricks postgres` CLI:
- **Project** `projects/dock-ops` (owner chad.macumber@databricks.com, pg17)
- **Branch** `production` — state `READY`
- **Endpoint** `primary` — `ENDPOINT_TYPE_READ_WRITE`, state `ACTIVE`
- **Host** `ep-square-resonance-d8lt69ul.database.us-east-2.cloud.databricks.com`
- Connection uses a short-lived **OAuth token** (`generate-database-credential`) + `sslmode=require`.

> Design note: the managed UC synced-table path requires `CREATE CATALOG` on the shared
> metastore, which this principal does not hold. Operational serving is therefore
> implemented by loading the curated gold state directly into Lakebase Postgres over the
> OAuth-authenticated endpoint — the same store the app reads. Change Data Feed is enabled
> on `gold_dock_current_state` so a managed synced table can be swapped in once the
> metastore grant is available (see README).

## Verified by reading back FROM Postgres (PostgreSQL 17.11)
```
schema dock_ops:
  dock_ops.dock_current_state   -> 36 rows   (live dock board)
  dock_ops.staffing_forecast    -> 504 rows  (7-day forward plan, indexed on terminal,hour_ts)
```

### Live dock state served from Postgres (telemetry status × CV state)
```
ATL  available  empty=6   docked=3  loading=3
DFW  available  empty=2   docked=2  loading=5   |  DFW occupied docked=1
MEM  ...
```
(The `cv_state` is the latest camera-frame classification per door; `telemetry_status` is
the real-time occupancy — the board shows both.)

### Top understaffed hours served from Postgres (terminal, hour, forecast, scheduled, gap)
```
MEM 11 -> 17 vs 8 (gap 9)
MEM 10 -> 17 vs 8 (gap 9)
ATL 11 -> 15 vs 7 (gap 8)
```
The Databricks App queries these Postgres tables directly for its live board and staffing
panel (see Stage 8 app evidence).
