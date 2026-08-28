# Evidence · GenAI shift-briefing assistant + CV serving endpoint

## A) GenAI shift-briefing assistant (`notebooks/07_genai_assistant.py`, SUCCESS)
Grounds a Foundation Model in the governed gold tables (current dock status, 31-day
utilization/detention, forecast understaffed hours, detention-hotspot docks) and generates
an actionable shift briefing. Two paths:
- **Real-time (app):** `databricks-claude-sonnet-5` via the serving SDK.
- **Governed SQL function:** `dock_ops.generate_shift_brief(ops_context STRING)` wrapping
  `ai_query('databricks-meta-llama-3-3-70b-instruct', …)` — callable from SQL/Genie/warehouse.
  (Claude's pay-per-token endpoint isn't supported by `ai_query`'s batch path, so a
  batch-supported model backs the SQL function.)

### Real generated briefing (Claude Sonnet 5, grounded in live gold data)
```
# SHIFT BRIEFING — Dock Operations

Situation: Docks are physically clear network-wide (ATL 0/12, DFW 1/10, MEM 0/14 occupied),
but midday staffing gaps at MEM and ATL are driving elevated detention costs ($235,798
combined over 31 days), with MEM the worst offender at $91,642.

Top 3 Priority Actions:
1. MEM, 10:00–11:00 — Largest gap in network (fc 17 vs sched 8, gap of 9). Add +6 dockhands
   now to close majority of gap ahead of the 09:00–12:00 surge window.
2. ATL, 11:00 — Gap of 8 (fc 15 vs sched 7). Add +5 staff at ATL by 10:45 to preempt the
   11:00 spike; ATL-D08 is a top detention hotspot ($8,243) and can't absorb another
   understaffed hour.
3. DFW, 10:00 — Smaller gap (5, fc 11 vs sched 6) but rising trend. Add +3 staff at DFW to
   protect against DFW-D05 hotspot ($7,976) recurring.

Projected Impact: Closing the MEM 9–12 window alone should offset ~30–40% of its detention
run-rate ... proactive staffing costs less than the OT premium ...
```
The model cites the *real* numbers from the gold tables — it is genuinely grounded, not generic.

### Governed UC function output (Llama 3.3 70B via ai_query)
```
Shift Briefing — Terminal: MEM, Hour: 11, Current Staffing: 8 scheduled, 17 forecasted
Top 3 Prioritized Staffing Actions:
1. Increase headcount: Add 9 staff members to meet forecasted demand of 17.
2. Terminal optimization: efficient use of resources to minimize delays.
3. Hourly adjustment: monitor and adjust staffing to prevent bottlenecks.
Projected Impact: Detention expected to decrease ~30% with adequate staffing ...
```

## B) CV serving endpoint invocation (`dock-occupancy-cls`, state READY / NOT_UPDATING)
Real base64 PNG frames pulled from `silver_dock_images` were sent to the endpoint via
`serving_endpoints.query(dataframe_records=[{"image_b64": ...}])`:

```json
{
  "endpoint": "dock-occupancy-cls",
  "true_labels":  ["empty", "obstructed", "empty"],
  "predictions":  ["empty", "obstructed", "empty"],
  "match":        [true, true, true]
}
```
The pyfunc decodes the base64 image, featurizes it, and returns the predicted dock state —
a live, callable CV endpoint, not a batch artifact.
