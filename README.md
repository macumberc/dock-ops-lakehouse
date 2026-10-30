# Meridian Freight — Loading-Dock Utilization, Staffing & Monitoring

An **end-to-end Databricks lakehouse** that turns a logistics carrier's loading docks from
a blind spot into a managed asset. Built for the FE Bar as one integrated data journey —
Lakeflow → Unity Catalog → Lakebase → ML/CV + GenAI → Genie → a Databricks App — running
live in the `fedex-fevm` workspace on **synthetic data only**.

> **Meridian Freight Systems** is a fictional national LTL carrier operating 3 cross-dock
> terminals (Atlanta 12 doors, Dallas 10, Memphis 14). Trailers arrive in unpredictable
> waves; a fixed shift plan misses the mid-day loading crunch, driving **$235,940 detention
> fees + $108,780 modeled overtime over 31 days (~$4.1M/yr)**. This build gives supervisors
> real-time dock visibility, a staffing-demand forecast, natural-language analytics, and an
> AI shift-briefing assistant.

## The end-to-end journey (all six stages, integrated)

| # | Stage | What it does | Evidence |
|---|-------|--------------|----------|
| 1 | **Data generation** | 45,745 telemetry events + 576 dock-camera images (deterministic, synthetic) → governed Volume | [evidence/01](evidence/01_data_generation.md) |
| 2 | **Lakeflow ingest** | Auto Loader inside a Declarative Pipeline: bronze streaming tables → sessionized silver (9,149 visits) with data-quality expectations | [evidence/02](evidence/02_lakeflow_ingest.md) |
| 3 | **Gold transforms** | Hourly utilization, terminal demand vs capacity + labor plan, live dock state | [evidence/03](evidence/03_gold_transform.md) |
| 4 | **Unity Catalog governance** | Column mask on worker IDs (ABAC), tags (respecting governed policies), role-based grants, full bronze→silver→gold lineage | [evidence/04](evidence/04_governance.md) |
| 5 | **CV classifier** | RandomForest pyfunc over base64 PNGs → UC-registered `dock_occupancy@prod`, served live; 100% holdout accuracy | [evidence/05](evidence/05_cv_model.md) |
| 6 | **Staffing forecast** | GradientBoosting `dock_demand_forecast@prod`; 7-day forward plan (241 understaffed weekday hours, $27k projected OT) | [evidence/06](evidence/06_forecast.md) |
| 7 | **GenAI + CV serving** | Grounded Claude Sonnet 5 shift briefing + governed `ai_query` UC function; live CV endpoint invocation | [evidence/07](evidence/07_genai_and_serving.md) |
| 8 | **Lakebase serving** | Autoscaling Postgres project; live dock board + staffing plan served from PG 17 | [evidence/08](evidence/08_lakebase.md) |
| 9 | **Genie room** | NL → SQL over 5 gold tables; Conversation-API Q&A captured | [evidence/09](evidence/09_genie.md) |
| 10 | **Databricks App** | FastAPI + React ops console (deployed, RUNNING); reads Lakebase + warehouse + serving | [evidence/10](evidence/10_app.md) |

**Every stage committed its real execution output as text** under [`evidence/`](evidence/)
(row counts, model metrics, confusion matrices, query results, generated briefings, deployed
API responses). The build was executed on the `fedex-fevm` workspace; the evidence is the
captured output of those runs.

## Architecture

```
 Synthetic gen        Lakeflow (SDP)          Unity Catalog (governed throughout)
 telemetry JSON  ─┐   ┌ bronze_telemetry ─┐   ┌ silver_visits ─┐   ┌ gold_terminal_hourly ─┐
 camera PNGs   ───┼──►│ bronze_dock_images├──►│ silver_dock_images ├─►│ gold_dock_utilization │
   → UC Volume    │   └───────────────────┘   └────────────────┘   │ gold_dock_current_state│
                  │                                                 │ gold_staffing_forecast │
                  │                                                 │ gold_visit_fact        │
                  │                                                 └───────────┬────────────┘
   CV model  ◄────┼── silver_dock_images (images)                               │
   (UC + serving) │                                    ┌────────────────────────┼───────────────┐
   Forecast  ◄────┴── gold_terminal_hourly             ▼                        ▼               ▼
   (UC)                                          Lakebase Postgres        Genie room     GenAI briefing
                                                 (live board+staffing)   (NL → SQL)     (Claude Sonnet 5)
                                                          │                                     │
                                                          └──────────────► Databricks App ◄──────┘
                                                              (FastAPI + React ops console)
```

## Presentation deck & demo script
- Google Slides deck with editable charts/tables, architecture, and timed presenter notes:
  **[Meridian Freight — Dock Operations Intelligence](https://docs.google.com/presentation/d/1aHc3m1N-RoiVbmZy3XPoPNjJ76ItUt88AKvzdas3T2c/edit)**.
  Twelve main slides and two optional appendices support 19 minutes of prepared material plus six minutes of discussion.
- Submission-ready PDF export: **[`output/pdf/meridian-freight-dock-operations.pdf`](output/pdf/meridian-freight-dock-operations.pdf)**.
- The prior HTML deck remains at [`deck/index.html`](deck/index.html). Use the Google Slides version for the current delivery and explicit pilot-economics assumptions.
- Roleplay demo script for presenting to the business + technical stakeholders (tell-show-tell
  flow, timed segments, and eight evidence-backed objection drills across both altitudes):
  **[`demo/roleplay_demo_script.md`](demo/roleplay_demo_script.md)**.

## Workspace presentation walkthrough

[`notebooks/00_demo_walkthrough.py`](notebooks/00_demo_walkthrough.py) provides a read-only,
presenter-friendly tour of the demo. It retains observation and forecast dates and reconciles
detention and modeled overtime against their source formulas. The
**[published walkthrough](https://fevm-fedex-fevm.cloud.databricks.com/#notebook/3195548178609337)**
passed serverless validation on October 15, 2026. Reconciliation recovered $141.51
of arrival-hour detention omitted by the original gold aggregation. Current detention is
$235,940.19 and combined modeled cost is $344,720.19. See
[`evidence/2026-10-15-data-reconciliation.md`](evidence/2026-10-15-data-reconciliation.md).

After authenticating `fedex-fevm` and confirming its current catalog, publish the notebooks
and saved evidence into your isolated workspace folder and run serverless validation:

```bash
uv run --no-project python scripts/publish_workspace_demo.py \
  --profile fedex-fevm --catalog <verified_workspace_catalog>
```

The publisher records the notebook URL and actual run result in
`evidence/workspace-demo-current.json`. It checks the identity, host, schema, and required
tables before writing. It does not rebuild the original underlying resources. To remove
only the new presenter folder, run the same command with `--teardown-launcher`.

## Run it yourself
Requires the Databricks CLI authenticated to a workspace (`--profile fedex-fevm`) and a Python venv.

```bash
pip install -e .                       # install the dock_ops package
# 1. generate synthetic data + run the pipeline/models via the numbered notebooks:
python scripts/dbx_run.py notebooks/01_generate_data.py 01_generate_data
#    ... 02 (pipeline via CLI), 03 gold, 04 governance, 05 cv, 06 forecast, 07 genai
python scripts/lakebase_sync.py        # load operational tables into Lakebase
python scripts/genie_ask.py            # exercise the Genie room
# app: databricks apps deploy dock-ops-app --source-code-path /Workspace/.../apps/dock-ops-app
```

Notebook quick start (on Databricks):
```python
%pip install git+https://github.com/macumberc/dock-ops-lakehouse.git
from dock_ops import deploy
deploy(spark)     # generates synthetic data into the raw Volume
```

## Repo layout
- `src/dock_ops/` — pip-installable package: config, data generators, Lakebase helpers, `deploy()`/`teardown()`
- `notebooks/` — the executed stages (01–07)
- `scripts/` — orchestration (`dbx_run.py`), SQL (`dbsql.py`), Lakebase sync, Genie Q&A, teardown
- `app/` — FastAPI backend + React frontend + `app.yaml`
- `evidence/` — **committed text execution evidence for every stage**
- `deck/` — Google Slides manifest, editable deck specification, and rendered previews
- `data_samples/` — illustrative synthetic dock-camera frames

## Teardown
```bash
bash scripts/teardown.sh    # removes app, endpoint, Genie space, Lakebase project, pipeline, schema (CASCADE)
```

*All data is synthetic. No real customer data is used anywhere in this build.*
