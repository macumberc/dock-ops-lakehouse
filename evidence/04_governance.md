# Evidence · Stage 4 — Unity Catalog governance

**What ran:** `notebooks/04_governance.py` as a serverless job (result_state = SUCCESS).
Applies governance across the dock-ops objects in
`fedex_fevm_catalog.dock_ops_chad_macumber`.

## Column mask on the sensitive worker-id (ABAC)
A masking function gated on **group membership** (not a hardcoded user list) protects
`gold_visit_fact.worker_id`:

```sql
CREATE OR REPLACE FUNCTION mask_worker_id(worker STRING)
RETURN CASE WHEN is_account_group_member('dock_supervisors') THEN worker ELSE 'W-REDACTED' END;
ALTER TABLE gold_visit_fact ALTER COLUMN worker_id SET MASK mask_worker_id;
```

Evidence the mask is in force for this (non-supervisor) principal:
```
SELECT DISTINCT worker_id FROM gold_visit_fact  ->  ['W-REDACTED']
```

## Classification tags (7 applied, 0 failed)
> **Governance signal:** this workspace enforces **governed tag policies** — key
> `data_domain` only permits value `train`, key `pii` only permits `ssn`/`address`.
> `worker_id` is an internal id, not SSN/address, so the build respects the governed
> keys and uses free-form keys rather than mislabel the column.

- Schema: `mfs_project=fe_bar_dock_ops`, `mfs_data_class=synthetic`, `mfs_domain=logistics`
- `gold_visit_fact`: `layer=gold`, `contains_worker_id=true`; column `worker_id`: `mfs_sensitivity=confidential`
- `gold_terminal_hourly`: `layer=gold`, `business_ready=true`
- `gold_dock_current_state`: `layer=gold`, `serving=lakebase`

## Role-based grants — analysts get the curated gold layer only
`SHOW GRANTS ON gold_dock_current_state`:
```
account users                : SELECT
chad.macumber@databricks.com : ALL PRIVILEGES
chad.macumber@databricks.com : MANAGE
```
Bronze/silver remain restricted to the owner; only the three business-facing gold
tables are granted to `account users`.

## Lineage — the whole DAG is captured by Unity Catalog
`system.access.table_lineage` (target schema = `dock_ops_chad_macumber`):
```
bronze_telemetry            -> silver_visits
bronze_dock_images          -> silver_dock_images
silver_visits               -> gold_dock_utilization_hourly
silver_visits               -> gold_terminal_hourly
silver_visits               -> gold_dock_current_state
gold_dock_utilization_hourly-> gold_terminal_hourly
```

## Object inventory (all in one governed schema)
- **Tables:** bronze_telemetry, bronze_dock_images, silver_visits, silver_dock_images,
  gold_visit_fact, gold_dock_utilization_hourly, gold_terminal_hourly, gold_dock_current_state
- **Functions:** mask_worker_id
- **Column comments** applied on wait_minutes, detention_fee_usd, worker_id, labor_gap.
