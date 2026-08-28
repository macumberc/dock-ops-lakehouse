# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Lakeflow Declarative Pipeline — ingest raw dock data (bronze → silver)
# MAGIC Meridian Freight Systems. Auto Loader (`cloudFiles`) streams raw files from the
# MAGIC governed UC Volume into bronze streaming tables; materialized views sessionize the
# MAGIC event stream into per-visit silver rows and parse the dock-camera image labels.
# MAGIC Data-quality **expectations** produce pass/drop metrics in the pipeline event log.
# MAGIC
# MAGIC This file is the *source* of a Lakeflow Declarative Pipeline (SDP). It is not run
# MAGIC directly — the pipeline is created/started via the CLI and its event log is the
# MAGIC committed run evidence.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

RAW = "/Volumes/fedex_fevm_catalog/dock_ops_chad_macumber/raw"

# Business constants (mirror dock_ops.config so the pipeline is self-contained).
DETENTION_FREE_HOURS = 2.0
DETENTION_FEE_PER_HOUR = 75.0

# COMMAND ----------
# MAGIC %md ### Bronze — raw telemetry event stream (Auto Loader, JSON)

# COMMAND ----------

@dlt.table(
    name="bronze_telemetry",
    comment="Raw dock telemetry events (gate + dock scans) ingested from the raw Volume via Auto Loader.",
    table_properties={"quality": "bronze"},
)
def bronze_telemetry():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaLocation", f"{RAW}/_schema/telemetry")
        .load(f"{RAW}/telemetry")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )

# COMMAND ----------
# MAGIC %md ### Bronze — dock-camera images (Auto Loader, binaryFile)

# COMMAND ----------

@dlt.table(
    name="bronze_dock_images",
    comment="Raw dock-camera image files (binary) ingested from the raw Volume via Auto Loader.",
    table_properties={"quality": "bronze"},
)
def bronze_dock_images():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .option("cloudFiles.schemaLocation", f"{RAW}/_schema/images")
        .option("pathGlobFilter", "*.png")
        .load(f"{RAW}/dock_images")
        .withColumn("_ingested_at", F.current_timestamp())
    )

# COMMAND ----------
# MAGIC %md ### Silver — sessionize telemetry into per-visit rows (with expectations)

# COMMAND ----------

@dlt.table(
    name="silver_visits",
    comment="One row per trailer visit: pivoted event timestamps + computed waits, dwell, and detention economics.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_visit", "gate_in IS NOT NULL AND gate_out IS NOT NULL")
@dlt.expect_or_drop("non_negative_dwell", "dwell_minutes >= 0")
@dlt.expect("has_dock", "dock_id IS NOT NULL")
def silver_visits():
    b = dlt.read("bronze_telemetry")
    # Pivot the 5 causal events per visit into columns.
    pivoted = (
        b.groupBy("visit_id", "terminal", "terminal_name", "trailer_id", "direction", "freight_weight_lbs")
        .agg(
            F.min(F.when(F.col("event_type") == "gate_in", F.to_timestamp("event_ts"))).alias("gate_in"),
            F.min(F.when(F.col("event_type") == "dock_assigned", F.to_timestamp("event_ts"))).alias("dock_assigned"),
            F.min(F.when(F.col("event_type") == "load_start", F.to_timestamp("event_ts"))).alias("load_start"),
            F.min(F.when(F.col("event_type") == "load_end", F.to_timestamp("event_ts"))).alias("load_end"),
            F.min(F.when(F.col("event_type") == "gate_out", F.to_timestamp("event_ts"))).alias("gate_out"),
            F.max(F.when(F.col("event_type") == "dock_assigned", F.col("dock_id"))).alias("dock_id"),
            F.max(F.when(F.col("event_type") == "load_start", F.col("worker_id"))).alias("worker_id"),
        )
    )
    mins = lambda a, b: (F.col(a).cast("long") - F.col(b).cast("long")) / 60.0
    out = (
        pivoted
        .withColumn("wait_minutes", mins("dock_assigned", "gate_in"))
        .withColumn("spot_minutes", mins("load_start", "dock_assigned"))
        .withColumn("load_minutes", mins("load_end", "load_start"))
        .withColumn("dwell_minutes", mins("gate_out", "gate_in"))
        .withColumn(
            "detention_hours",
            F.greatest(F.lit(0.0), F.col("wait_minutes") / 60.0 - F.lit(DETENTION_FREE_HOURS)),
        )
        .withColumn("detention_fee_usd", F.round(F.col("detention_hours") * F.lit(DETENTION_FEE_PER_HOUR), 2))
        .withColumn("visit_date", F.to_date("gate_in"))
        .withColumn("gate_in_hour", F.date_trunc("hour", "gate_in"))
    )
    return out

# COMMAND ----------
# MAGIC %md ### Silver — parse dock-camera image labels from filenames

# COMMAND ----------

@dlt.table(
    name="silver_dock_images",
    comment="Dock-camera images with parsed terminal/dock/timestamp and ground-truth label; retains binary content for CV scoring.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_label", "true_label IN ('empty','docked','loading','obstructed')")
def silver_dock_images():
    b = dlt.read("bronze_dock_images")
    # Filename: {TERMINAL}_{DOCK}_{YYYYMMDDHHMM}_{LABEL}.png
    fname = F.element_at(F.split(F.col("path"), "/"), -1)
    base = F.regexp_replace(fname, r"\.png$", "")
    parts = F.split(base, "_")
    return (
        b.withColumn("file_name", fname)
        .withColumn("terminal", parts.getItem(0))
        .withColumn("dock_id", parts.getItem(1))
        .withColumn("frame_ts", F.to_timestamp(parts.getItem(2), "yyyyMMddHHmm"))
        .withColumn("true_label", parts.getItem(3))
        .select("path", "file_name", "terminal", "dock_id", "frame_ts", "true_label", "content", "length", "_ingested_at")
    )
