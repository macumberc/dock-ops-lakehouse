# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate synthetic dock telemetry + camera images
# MAGIC Meridian Freight Systems — FE Bar build. Lands raw synthetic data into the
# MAGIC governed UC Volume `fedex_fevm_catalog.dock_ops_chad_macumber.raw`:
# MAGIC - `telemetry/` — newline-delimited JSON event stream (gate + dock events)
# MAGIC - `dock_images/` — labeled PNG dock-camera frames (4 states)
# MAGIC
# MAGIC The `dock_ops` wheel is installed as a serverless environment dependency.
# MAGIC All data is synthetic — no real customer data.

# COMMAND ----------

# DBTITLE 1,Generate + land raw data
import json
from dock_ops import deploy, config

# deploy() generates the event stream and renders per-door camera images,
# writing both into the raw Volume via the /Volumes FUSE mount.
summary = deploy(spark, images_per_door=16)
print("Telemetry:", json.dumps(summary["telemetry"], indent=2))
print("Images:", json.dumps(summary["images"], indent=2))

# COMMAND ----------

# DBTITLE 1,Verify files landed in the Volume
tel_dir = config.volume_path("telemetry")
img_dir = config.volume_path("dock_images")
tel_files = dbutils.fs.ls(f"dbfs:{tel_dir}")
img_files = dbutils.fs.ls(f"dbfs:{img_dir}")
print(f"telemetry files landed: {len(tel_files)}")
print(f"image files landed:     {len(img_files)}")
print("first 3 telemetry files:", [f.name for f in tel_files[:3]])
print("first 3 image files:    ", [f.name for f in img_files[:3]])

# COMMAND ----------

# DBTITLE 1,Peek one raw telemetry file (evidence)
sample = spark.read.json(f"dbfs:{tel_dir}/{tel_files[0].name}")
sample.printSchema()
sample.show(5, truncate=False)

# COMMAND ----------

# DBTITLE 1,Exit with a machine-readable summary for evidence capture
result = {
    "telemetry_events": summary["telemetry"]["events"],
    "telemetry_days": summary["telemetry"]["days"],
    "telemetry_files": len(tel_files),
    "images_total": summary["images"]["images"],
    "images_by_label": summary["images"]["by_label"],
    "image_size": summary["images"]["size"],
    "telemetry_dir": tel_dir,
    "images_dir": img_dir,
}
dbutils.notebook.exit(json.dumps(result))
