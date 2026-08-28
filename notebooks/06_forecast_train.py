# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Staffing-demand forecast
# MAGIC Meridian Freight Systems. Learns dock-labor demand from `gold_terminal_hourly`
# MAGIC (hour-of-day, day-of-week, terminal) and forecasts the **recommended dock headcount**
# MAGIC for the next 24 hours per terminal, then writes a forward-looking
# MAGIC `gold_staffing_forecast` that flags the shifts the fixed plan will under-staff.
# MAGIC Model is logged to MLflow and registered in Unity Catalog. Serverless CPU.

# COMMAND ----------

import json
from datetime import timedelta
import numpy as np
import pandas as pd
import mlflow
from mlflow.models.signature import infer_signature
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

S = "fedex_fevm_catalog.dock_ops_chad_macumber"
MODEL = f"{S}.dock_demand_forecast"
TERMINALS = ["ATL", "DFW", "MEM"]
DOORS = {"ATL": 12, "DFW": 10, "MEM": 14}
BASE_HOURLY_LABOR = 28.0

# COMMAND ----------
# DBTITLE 1,Load the terminal-hour training table
pdf = spark.table(f"{S}.gold_terminal_hourly").toPandas()
pdf["hour_ts"] = pd.to_datetime(pdf["hour_ts"])
pdf = pdf.sort_values("hour_ts")
print("terminal-hour rows:", len(pdf), "| span:", pdf["hour_ts"].min(), "->", pdf["hour_ts"].max())

FEATURES = ["hour_of_day", "day_of_week", "is_weekend", "door_count", "term_ATL", "term_DFW", "term_MEM"]

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["is_weekend"] = x["day_of_week"].isin([1, 7]).astype(int)  # Spark dayofweek: 1=Sun,7=Sat
    for t in TERMINALS:
        x[f"term_{t}"] = (x["terminal"] == t).astype(int)
    return x[FEATURES]

# COMMAND ----------
# DBTITLE 1,Time-based train/test split (last 5 days held out)
cutoff = pdf["hour_ts"].max() - pd.Timedelta(days=5)
train = pdf[pdf["hour_ts"] <= cutoff]
test = pdf[pdf["hour_ts"] > cutoff]
Xtr, ytr = build_features(train), train["recommended_headcount"].astype(float)
Xte, yte = build_features(test), test["recommended_headcount"].astype(float)
print(f"train rows: {len(Xtr)} | test rows: {len(Xte)}")

# Deeper trees so the model can isolate individual peak hours (hour_of_day has 24
# distinct values across 3 terminals — shallow trees underfit the mid-day crunch).
model = GradientBoostingRegressor(n_estimators=400, max_depth=6, learning_rate=0.05,
                                  subsample=0.8, random_state=42)
model.fit(Xtr, ytr)
pred = model.predict(Xte)
mae = float(mean_absolute_error(yte, pred))
r2 = float(r2_score(yte, pred))
# naive baseline = predict per-hour mean from train
hourly_mean = train.groupby("hour_of_day")["recommended_headcount"].mean()
naive = test["hour_of_day"].map(hourly_mean).fillna(train["recommended_headcount"].mean())
mae_naive = float(mean_absolute_error(yte, naive))
print(f"MAE={mae:.3f}  R2={r2:.3f}  (naive hourly-mean MAE={mae_naive:.3f})")

# COMMAND ----------
# DBTITLE 1,Log + register in Unity Catalog + set prod alias
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment("/Users/chad.macumber@databricks.com/dock_ops/forecast_experiment")
signature = infer_signature(Xtr, pred)
with mlflow.start_run(run_name="dock_demand_gbr") as run:
    mlflow.log_params({"model": "GradientBoostingRegressor", "n_estimators": 400,
                       "max_depth": 6, "learning_rate": 0.05, "subsample": 0.8,
                       "features": ",".join(FEATURES)})
    mlflow.log_metric("test_mae", mae)
    mlflow.log_metric("test_r2", r2)
    mlflow.log_metric("naive_mae", mae_naive)
    mlflow.log_metric("mae_improvement_vs_naive_pct", round((mae_naive - mae) / mae_naive * 100, 1))
    mlflow.sklearn.log_model(model, artifact_path="model", signature=signature,
                             input_example=Xtr.head(3), registered_model_name=MODEL)
    run_id = run.info.run_id

client = mlflow.MlflowClient()
ver = max(int(m.version) for m in client.search_model_versions(f"name='{MODEL}'"))
client.set_registered_model_alias(MODEL, "prod", ver)
print(f"registered {MODEL} version {ver} alias prod")

# COMMAND ----------
# DBTITLE 1,Forecast the next 7 days per terminal -> gold_staffing_forecast
# Start at the next midnight so the horizon spans full operating days incl. weekdays
# (the day right after the data window is a weekend, which is genuinely low-volume).
HORIZON_HOURS = 24 * 7
horizon_start = (pdf["hour_ts"].max() + pd.Timedelta(days=1)).normalize()
rows = []
for h in range(HORIZON_HOURS):
    ts = horizon_start + pd.Timedelta(hours=h)
    dow = (ts.dayofweek + 1) % 7 + 1  # convert to Spark 1=Sun..7=Sat
    for t in TERMINALS:
        rows.append({"terminal": t, "hour_ts": ts, "hour_of_day": ts.hour,
                     "day_of_week": dow, "door_count": DOORS[t]})
future = pd.DataFrame(rows)
future["forecast_headcount"] = np.ceil(model.predict(build_features(future))).astype(int).clip(min=0)
# fixed shift plan (same rule as gold_terminal_hourly)
def scheduled(row):
    h = row["hour_of_day"]
    if 6 <= h <= 13 or 14 <= h <= 21:
        return round(row["door_count"] * 0.55)
    return round(row["door_count"] * 0.25)
future["scheduled_headcount"] = future.apply(scheduled, axis=1).astype(int)
future["labor_gap"] = future["forecast_headcount"] - future["scheduled_headcount"]
future["projected_overtime_cost_usd"] = (future["labor_gap"].clip(lower=0) * BASE_HOURLY_LABOR * 1.5).round(2)
future["understaffed"] = future["labor_gap"] > 0

sdf = spark.createDataFrame(future)
(sdf.write.mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(f"{S}.gold_staffing_forecast"))
spark.sql(f"ALTER TABLE {S}.gold_staffing_forecast SET TAGS ('layer'='gold','serving'='app')")
print("gold_staffing_forecast rows:", sdf.count())

# COMMAND ----------
# DBTITLE 1,Evidence
future["is_weekday"] = ~future["day_of_week"].isin([1, 7])
understaffed_hours = int(future["understaffed"].sum())
weekday_understaffed = int(future[future["is_weekday"]]["understaffed"].sum())
sample = future[future["understaffed"]].sort_values("labor_gap", ascending=False).head(8)
sample_records = sample[["terminal", "hour_of_day", "forecast_headcount",
                         "scheduled_headcount", "labor_gap", "projected_overtime_cost_usd"]].to_dict("records")
result = {
    "test_mae": round(mae, 3),
    "test_r2": round(r2, 3),
    "naive_mae": round(mae_naive, 3),
    "mae_improvement_vs_naive_pct": round((mae_naive - mae) / mae_naive * 100, 1),
    "model": MODEL, "model_version": ver, "run_id": run_id,
    "forecast_horizon_hours": HORIZON_HOURS,
    "understaffed_terminal_hours": understaffed_hours,
    "weekday_understaffed_terminal_hours": weekday_understaffed,
    "top_understaffed": sample_records,
    "total_projected_overtime_next_7d_usd": round(float(future["projected_overtime_cost_usd"].sum()), 2),
}
print(json.dumps(result, indent=2, default=str))
dbutils.notebook.exit(json.dumps(result, default=str))
