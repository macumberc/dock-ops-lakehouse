# Evidence · Stage 6 — Staffing-demand forecast

**What ran:** `notebooks/06_forecast_train.py` as a serverless (CPU) job. Learns dock-labor
demand from `gold_terminal_hourly` and forecasts the recommended headcount for the next 7
days per terminal, writing a forward-looking `gold_staffing_forecast`. **result_state = SUCCESS.**

- Model: `fedex_fevm_catalog.dock_ops_chad_macumber.dock_demand_forecast` (UC), alias `@prod`
- Algorithm: GradientBoostingRegressor (400 trees, depth 6) on
  `[hour_of_day, day_of_week, is_weekend, door_count, terminal]`.

## Held-out performance (time-based split — last 5 days held out)
| metric | value |
| --- | --- |
| test MAE (headcount) | **1.885** |
| test R² | **0.606** |
| naive hourly-mean baseline MAE | 1.997 |
| improvement vs naive | **+5.6%** |

Hourly trailer flow is Poisson-distributed, so per-hour counts carry irreducible
variance; R²≈0.61 and beating a strong diurnal-mean baseline is an honest result for
count forecasting. The business value is in the **forward staffing plan** below.

## Forward staffing plan (next 7 days → `gold_staffing_forecast`)
- **241 weekday terminal-hours** are forecast to be **understaffed** by the fixed plan.
- **$27,426 projected overtime** across the 7-day horizon.

Top understaffed weekday hours (the mid-day loading crunch the fixed shifts miss):
| terminal | hour | forecast_headcount | scheduled | labor_gap | proj_overtime_usd |
| --- | --- | --- | --- | --- | --- |
| MEM | 10 | 17 | 8 | +9 | 378 |
| MEM | 11 | 17 | 8 | +9 | 378 |
| ATL | 11 | 15 | 7 | +8 | 336 |
| MEM | 11 | 16 | 8 | +8 | 336 |

The forecast tells supervisors *where and when* to move labor — pull headcount from the
over-staffed overnight shift into the 10:00–12:00 (and evening) peaks.

## MLflow (text) metrics logged
`test_mae`, `test_r2`, `naive_mae`, `mae_improvement_vs_naive_pct`, model params.
