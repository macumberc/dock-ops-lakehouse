# Evidence · Stage 8 — Genie room (natural-language querying)

**What ran:** `scripts/genie_ask.py` against Genie space **`Meridian Dock Utilization`**
(`space_id 01f1a3243b00149fa4876211f8b5c004`), created over the five gold tables with
curated text instructions and example SQL. Questions asked via the Conversation API; each
question → generated SQL → result rows captured below (all `status = COMPLETED`).

## Q1 — "Which terminal has the highest total detention fees?"
Generated SQL:
```sql
WITH terminal_fees AS (
  SELECT terminal, ROUND(SUM(detention_fee_usd), 0) AS detention_usd
  FROM fedex_fevm_catalog.dock_ops_chad_macumber.gold_terminal_hourly
  GROUP BY terminal)
SELECT terminal, detention_usd FROM terminal_fees ORDER BY detention_usd DESC LIMIT 1
```
Result: `[["MEM", "91642.0"]]` — Memphis, $91,642 (matches the gold layer ✓).

## Q2 — "What hours of the day are we most understaffed next week?"
Generated SQL:
```sql
SELECT terminal, hour_of_day, MAX(labor_gap) AS max_gap
FROM fedex_fevm_catalog.dock_ops_chad_macumber.gold_staffing_forecast
WHERE labor_gap > 0 AND day_of_week NOT IN (1,7)
GROUP BY terminal, hour_of_day ORDER BY max_gap DESC LIMIT 10
```
Result:
```
MEM 11 -> 9 | MEM 10 -> 9 | ATL 11 -> 8 | ATL 12 -> 7 | MEM 9 -> 7
MEM 12 -> 7 | ATL 10 -> 5 | DFW 10 -> 5 | DFW 11 -> 5 | MEM 13 -> 5
```
(matches the forecast table ✓ — the mid-day crunch, Memphis worst.)

## Q3 — "How many docks are currently occupied at each terminal right now?"
Generated SQL:
```sql
SELECT terminal, COUNT(*) AS occupied_docks
FROM fedex_fevm_catalog.dock_ops_chad_macumber.gold_dock_current_state
WHERE telemetry_status = 'occupied' GROUP BY terminal
```
Result: `[["DFW", "1"]]` — one dock occupied at Dallas as of the latest telemetry (✓).

Genie correctly routes "detention" → `gold_terminal_hourly`, "next week" →
`gold_staffing_forecast`, and "right now" → `gold_dock_current_state`, exactly as the
text instructions specify.
