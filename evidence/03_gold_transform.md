# Evidence · Stage 3 — Gold transforms (utilization, demand, current state)

**What ran:** `notebooks/03_gold_transform.py` as a serverless job (result_state = SUCCESS).
Builds the governed analytics layer from `silver_visits`.

Notebook exit result:
```json
{
  "gold_dock_utilization_hourly_rows": 13801,
  "gold_terminal_hourly_rows": 2126,
  "gold_dock_current_state_rows": 36,
  "docks_occupied_now": 1,
  "total_detention_fee_usd": 235798.68,
  "total_overtime_cost_usd": 108780.00,
  "peak_hour_avg_util_pct": {"hour_of_day": 11, "avg_util_pct": 61.1, "avg_labor_gap": 3.11}
}
```

## The core problem, quantified (31 days, 3 terminals, 9,149 trailer visits)
- **Detention fees: $235,799** · **Avoidable overtime: $108,780** → combined **$344,579**
  over 31 days ≈ **$4.06M annualized**.

## The staffing mismatch (per-hour-of-day averages across terminals)
The fixed shift plan (`scheduled`) does not track demand: the **10:00–12:00 loading
crunch is understaffed** (positive labor gap) while **nights are over-staffed**.

| hour | avg_util_% | avg_arrivals | scheduled | recommended | labor_gap |
| --- | --- | --- | --- | --- | --- |
| 06 | 30.9 | 7.3 | 7.0 | 4.2 | -2.8 |
| 08 | 48.4 | 8.4 | 7.0 | 7.1 | 0.1 |
| 10 | 58.9 | 5.8 | 7.0 | 9.4 | **+2.4** |
| 11 | 61.1 | 4.9 | 7.0 | 10.1 | **+3.1** |
| 12 | 57.9 | 4.3 | 7.0 | 9.3 | **+2.3** |
| 20 | 54.2 | 2.1 | 7.0 | 8.2 | +1.2 |
| 02 | 12.9 | 1.1 | 3.4 | 1.9 | -1.5 |

## By terminal (31 days)
| terminal | detention_usd | overtime_usd | avg_util_% | peak_util_% |
| --- | --- | --- | --- | --- |
| ATL (Atlanta Gateway) | 75,277 | 36,498 | 39.8 | 87.6 |
| DFW (Dallas Regional) | 68,879 | 28,308 | 41.1 | 94.8 |
| MEM (Memphis Hub) | 91,642 | 43,974 | 39.7 | 93.3 |

Peak door utilization reaches **88–95%** while the plan leaves the mid-day loading
window short-handed — the gap this build's forecast + live monitoring closes.

## Tables produced (managed UC tables)
- `gold_dock_utilization_hourly` — 13,801 door-hour rows (occupancy, utilization %)
- `gold_terminal_hourly` — 2,126 terminal-hour rows (demand vs capacity, labor plan/gap) — forecast training table
- `gold_dock_current_state` — 36 door rows (live board base; augmented with CV in stage 4)
