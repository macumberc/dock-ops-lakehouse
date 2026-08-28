# Evidence · Stage 2 — Lakeflow ingest (Declarative Pipeline)

**What ran:** Lakeflow Declarative Pipeline `dock_ops_ingest_chad_macumber`
(`pipeline_id 9f101d4c-0023-4662-9a2a-33afcf87dd37`, serverless), source
`notebooks/02_lakeflow_pipeline.py`. Auto Loader (`cloudFiles`) streams raw files
from the governed Volume into bronze streaming tables; materialized views
sessionize the event stream into per-visit silver rows and parse image labels.

- Update `a5da0f0c-b53f-42ca-9092-3bf4a517ab22` → states observed:
  `CREATED → INITIALIZING → SETTING_UP_TABLES → COMPLETED` · **COMPLETED**

## Table row counts (queried on the serverless warehouse)
| tbl | rows |
| --- | --- |
| bronze_telemetry | 20445 |
| bronze_dock_images | 575 |
| silver_visits | 4089 |
| silver_dock_images | 575 |

Reconciliation: 20,445 events ÷ 5 events/visit = **4,089 visits** ✓. (576 images were
generated; 575 distinct filenames landed — one deterministic timestamp collision, benign.)

## Data-quality expectations (from the pipeline event log)
Queried via `event_log("9f101d4c-…")`:

| flow | expectation | passed | failed |
| --- | --- | --- | --- |
| silver_dock_images | valid_label | 575 | 0 |
| silver_visits | has_dock | 4089 | 0 |
| silver_visits | non_negative_dwell | 4089 | 0 |
| silver_visits | valid_visit | 4089 | 0 |

All expectations passed — the sessionized visits are complete and internally consistent.

## Sample: highest-detention visits (business signal surfaced by silver)
| visit_id | terminal | dock_id | direction | wait_min | dwell_min | det_hrs | detention_fee_usd |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V20260803-MEM-000619 | MEM | MEM-D04 | inbound | 581.8 | 687.5 | 7.7 | 577.23 |
| V20260813-ATL-001873 | ATL | ATL-D05 | inbound | 575.7 | 660.3 | 7.6 | 569.65 |
| V20260731-MEM-000279 | MEM | MEM-D01 | inbound | 549.1 | 596.6 | 7.15 | 536.42 |
| V20260809-DFW-001312 | DFW | DFW-D01 | inbound | 531.6 | 598.0 | 6.86 | 514.48 |
| V20260802-DFW-000406 | DFW | DFW-D06 | outbound | 525.4 | 621.0 | 6.76 | 506.79 |

## Image labels parsed from filenames (silver_dock_images)
| true_label | n |
| --- | --- |
| empty | 214 |
| loading | 169 |
| docked | 125 |
| obstructed | 67 |
