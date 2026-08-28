"""Meridian Freight Systems — loading-dock utilization, staffing & monitoring.

An end-to-end Databricks lakehouse: Lakeflow ingestion, Unity Catalog governance,
Lakebase operational serving, a computer-vision dock-occupancy classifier, a
utilization/staffing forecast, a GenAI shift-briefing assistant, a Genie room, and
a FastAPI + React operations app.

Quick start (Databricks notebook):
    %pip install git+https://github.com/macumberc/dock-ops-lakehouse.git
    from dock_ops import deploy
    deploy(spark)
"""

from dock_ops import config

__version__ = "0.1.0"
__all__ = ["config", "deploy", "teardown"]


def deploy(spark, images_per_door: int = 16) -> dict:
    """Generate synthetic data into the raw Volume (entry point for the demo).

    This is the notebook quick-start hook. It only lands raw data; the medallion
    pipeline, models, Genie space, Lakebase sync, and app are driven by the
    numbered notebooks / scripts so their execution evidence is captured as text.

    Args:
        spark: the active SparkSession (unused for generation but kept for the
            standard demo signature and future Spark-native steps).
        images_per_door: dock-camera snapshots to render per door.

    Returns:
        A summary dict of what was generated.
    """
    from dock_ops.data_gen import generate_events, generate_images, write_events_to_dir

    tel_dir = config.volume_path("telemetry")
    img_dir = config.volume_path("dock_images")
    events = generate_events()
    tel_summary = write_events_to_dir(events, tel_dir, files_per_day=1)
    img_summary = generate_images(img_dir, images_per_door=images_per_door)
    return {"telemetry": tel_summary, "images": img_summary}


def teardown(spark) -> None:
    """Drop everything this build created (schema CASCADE).

    Lakebase project, serving endpoints, the Genie space, and the app are torn
    down by scripts/teardown.sh (they live outside the schema).
    """
    spark.sql(f"DROP SCHEMA IF EXISTS {config.full_schema()} CASCADE")
