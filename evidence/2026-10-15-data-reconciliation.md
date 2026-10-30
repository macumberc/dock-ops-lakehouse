# Live data reconciliation, October 15, 2026

Workspace: `fedex-fevm`, `https://fevm-fedex-fevm.cloud.databricks.com`.
Data scope: fictional Meridian Freight, synthetic history July 30–August 29, 2026.

## Defect and repair

The first serverless walkthrough run deliberately failed its reconciliation check.
`silver_visits` summed to **$235,940.19** in detention, while the original gold
terminal-hour aggregation summed to **$235,798.68**, a **$141.51** shortfall.

An anti-join identified **15 arrival terminal-hours** omitted from gold because its
hour spine began with dock occupancy. Those hours contained arrivals waiting for a
door but no occupied door-minutes. Their detention fees were **$134.16 in Dallas**
and **$7.35 in Memphis**. The original hourly left join dropped both amounts.

`sql/repair_arrival_hours.sql` inserted only the missing 15 rows with an idempotent
MERGE. It updated and deleted zero existing rows. The corrected source notebook
now unions occupancy, arrival, and active-load hours before joining measures.
The repair leaves the CV dock snapshot and the captured staffing forecast intact.

## Reconciled baseline

| Terminal | Detention USD | Modeled overtime USD | Average utilization |
| --- | ---: | ---: | ---: |
| Atlanta | 75,277.09 | 36,498.00 | 39.4% |
| Dallas | 69,013.47 | 28,308.00 | 40.7% |
| Memphis | 91,649.63 | 43,974.00 | 39.6% |
| Total | **235,940.19** | **108,780.00** | **39.9%** |

Gold now has 2,141 terminal-hour rows. Combined modeled cost is **$344,720.19**.
Annualization is `$344,720.19 / 31 * 365 = $4,058,802.24`, approximately **$4.06M**.
Overtime independently recomputes from positive headcount gaps at `$28 * 1.5` per hour.

| Hour | Average scheduled workers | Average recommended workers |
| --- | ---: | ---: |
| 02:00 | 3.3 | 1.8 |
| 06:00 | 7.0 | 4.1 |
| 08:00 | 7.0 | 7.1 |
| 10:00 | 7.0 | 9.4 |
| 11:00 | 7.0 | 10.1 |
| 12:00 | 7.0 | 9.3 |
| 20:00 | 7.0 | 8.2 |

Older August evidence remains an accurate record of the original execution, but
its detention totals predate this correction. The Google Slides deck and current
walkthrough use the reconciled values. Forecast model metrics remain the recorded
evaluation of the original training snapshot; this repair did not retrain models.
