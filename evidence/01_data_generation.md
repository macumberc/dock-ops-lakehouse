# Evidence · Stage 1 — Synthetic data generation

**What ran:** `notebooks/01_generate_data.py` as a serverless job in `fedex-fevm`
(`dock_ops` wheel installed as an environment dependency), calling `dock_ops.deploy(spark)`.
Generation is fully deterministic (fixed `REFERENCE_DATE` + RNG seeds), so re-runs
reproduce identical files and counts. **result_state = SUCCESS.**

## Raw data landed in the governed Volume
`/Volumes/fedex_fevm_catalog/dock_ops_chad_macumber/raw/`

Notebook exit result (captured from `notebook_output.result`):
```json
{
  "telemetry_events": 45745,
  "telemetry_days": 31,
  "telemetry_files": 31,
  "images_total": 576,
  "images_by_label": {"empty": 214, "docked": 126, "loading": 169, "obstructed": 67},
  "image_size": [192, 144],
  "telemetry_dir": "/Volumes/fedex_fevm_catalog/dock_ops_chad_macumber/raw/telemetry",
  "images_dir": "/Volumes/fedex_fevm_catalog/dock_ops_chad_macumber/raw/dock_images"
}
```

## What the data represents
- **45,745 telemetry events** over **31 days** across 3 terminals (Atlanta 12 doors,
  Dallas 10, Memphis 14). Each trailer *visit* emits 5 causal events —
  `gate_in → dock_assigned → load_start → load_end → gate_out` — landed as
  newline-delimited JSON, one file per event-date (31 files) so Auto Loader sees a
  realistic file trickle. → **9,149 visits** (45,745 ÷ 5).
- **576 dock-camera images** (192×144 PNG) labeled across four states
  (`empty`, `docked`, `loading`, `obstructed`); the ground-truth label is encoded in
  the filename `{TERMINAL}_{DOCK}_{YYYYMMDDHHMM}_{LABEL}.png`. (575 distinct filenames
  land after one benign deterministic timestamp collision.)

Arrival intensity is modeled as a morning inbound wave and an afternoon/evening
outbound cutoff crunch, with door-assignment waits that balloon under peak
congestion — the source of the detention-fee and overtime story this build solves.

## Raw telemetry schema (from the notebook run)
```
root
 |-- direction: string        (inbound | outbound)
 |-- dock_id: string          (e.g. ATL-D07; null for gate_in)
 |-- event_id: string
 |-- event_ts: string         (ISO-8601)
 |-- event_type: string       (gate_in | dock_assigned | load_start | load_end | gate_out)
 |-- freight_weight_lbs: long
 |-- terminal: string         (ATL | DFW | MEM)
 |-- terminal_name: string
 |-- trailer_id: string
 |-- visit_id: string         (ties the 5 events of one visit together)
 |-- worker_id: string        (null except on load_start/load_end)
```

Sample synthetic dock-camera frames (one per class) are committed under `data_samples/`.
