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
| bronze_telemetry | 45745 |
| bronze_dock_images | 575 |
| silver_visits | 9149 |
| silver_dock_images | 575 |

Reconciliation: 45,745 events ÷ 5 events/visit = **9,149 visits** ✓. (576 images were
generated; 575 distinct filenames landed — one deterministic timestamp collision, benign.)

## Data-quality expectations (from the pipeline event log)
Queried via `event_log("9f101d4c-…")`:

| flow | expectation | passed | failed |
| --- | --- | --- | --- |
| silver_dock_images | valid_label | 575 | 0 |
| silver_visits | has_dock | 9149 | 0 |
| silver_visits | non_negative_dwell | 9149 | 0 |
| silver_visits | valid_visit | 9149 | 0 |

All expectations passed — the sessionized visits are complete and internally consistent.

## Sample: highest-detention visits (business signal surfaced by silver)
| visit_id | terminal | dock_id | direction | wait_min | dwell_min | det_hrs | detention_fee_usd |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V20260810-ATL-003197 | ATL | ATL-D08 | outbound | 811.3 | 897.6 | 11.52 | 864.15 |
| V20260822-DFW-007131 | DFW | DFW-D08 | outbound | 759.1 | 853.1 | 10.65 | 798.88 |
| V20260731-MEM-000621 | MEM | MEM-D04 | inbound | 581.8 | 716.4 | 7.70 | 577.23 |
| V20260828-MEM-009125 | MEM | MEM-D04 | inbound | 550.2 | 655.2 | 7.17 | 537.77 |
| V20260730-MEM-000279 | MEM | MEM-D01 | inbound | 549.1 | 616.9 | 7.15 | 536.42 |

## Image labels parsed from filenames (silver_dock_images)
| true_label | n |
| --- | --- |
| empty | 214 |
| loading | 169 |
| docked | 125 |
| obstructed | 67 |
