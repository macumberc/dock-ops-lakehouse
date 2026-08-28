"""Central configuration for the Meridian Freight dock-ops lakehouse build.

Every object name, warehouse id, and Foundation Model endpoint used across the
end-to-end journey lives here so notebooks, jobs, and the app stay consistent.
No secrets are stored in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Unity Catalog placement (user-scoped schema per house conventions) -------
CATALOG: str = "fedex_fevm_catalog"
SCHEMA: str = "dock_ops_chad_macumber"
VOLUME: str = "raw"

# --- Confirmed workspace resources (fedex-fevm) -------------------------------
# Serverless PRO SQL warehouse verified live in the workspace. The app and the
# evidence-capture scripts auto-detect a serverless warehouse and fall back to
# this id; nothing else is hardcoded.
DEFAULT_WAREHOUSE_ID: str = "2a0649a9f0fb7773"

# Foundation Model endpoint backing the GenAI shift-briefing assistant.
GENAI_ENDPOINT: str = "databricks-claude-sonnet-5"

# --- Model / serving names ----------------------------------------------------
CV_MODEL_NAME: str = "dock_occupancy"          # UC: {CATALOG}.{SCHEMA}.dock_occupancy
FORECAST_MODEL_NAME: str = "dock_demand_forecast"
CV_ENDPOINT: str = "dock-occupancy-cls"
MODEL_ALIAS: str = "prod"

# --- Lakebase -----------------------------------------------------------------
LAKEBASE_PROJECT: str = "dock-ops"
LAKEBASE_PG_CATALOG: str = "dock_pg"            # UC catalog registered over Postgres
LAKEBASE_BRANCH: str = "production"

# --- Genie --------------------------------------------------------------------
GENIE_TITLE: str = "Meridian Dock Utilization"

# --- Databricks App -----------------------------------------------------------
APP_NAME: str = "dock-ops-app"


def full_schema() -> str:
    """Return the fully qualified `catalog.schema`."""
    return f"{CATALOG}.{SCHEMA}"


def table(name: str) -> str:
    """Return a fully qualified table name inside the build schema."""
    return f"{CATALOG}.{SCHEMA}.{name}"


def volume_path(*parts: str) -> str:
    """Return a /Volumes path inside the raw landing volume."""
    base = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"
    return "/".join([base, *parts]) if parts else base


def model_full_name(name: str) -> str:
    """Return the fully qualified UC model name."""
    return f"{CATALOG}.{SCHEMA}.{name}"


# --- Business / simulation model ---------------------------------------------
# Meridian Freight Systems: a fictional national less-than-truckload (LTL)
# carrier. These constants drive the synthetic data generator so the story
# (idle mornings, overwhelmed afternoons, detention fees, overtime) is coherent
# across telemetry, images, the forecast, and the KPIs shown in the app.

# Single-token labels (no underscores) so they parse cleanly from the
# `_`-delimited image filenames. "docked" == trailer backed in, no activity.
DOCK_STATES: tuple[str, ...] = ("empty", "docked", "loading", "obstructed")


@dataclass(frozen=True)
class Terminal:
    """A Meridian cross-dock terminal."""

    code: str
    name: str
    doors: int


TERMINALS: tuple[Terminal, ...] = (
    Terminal("ATL", "Atlanta Gateway", 12),
    Terminal("DFW", "Dallas Regional", 10),
    Terminal("MEM", "Memphis Hub", 14),
)

# Simulation window and economics.
HISTORY_DAYS: int = 30
DETENTION_FREE_HOURS: float = 2.0          # free time before detention accrues
DETENTION_FEE_PER_HOUR: float = 75.0       # USD per trailer-hour of detention
OVERTIME_MULTIPLIER: float = 1.5           # labor cost multiplier past 8h/shift
BASE_HOURLY_LABOR: float = 28.0            # USD/hr per dock worker
TRAILERS_PER_WORKER_PER_HOUR: float = 1.6  # throughput capacity per worker
RANDOM_SEED: int = 20260828


@dataclass(frozen=True)
class BuildConfig:
    """Convenience bundle passed to generators and jobs."""

    catalog: str = CATALOG
    schema: str = SCHEMA
    volume: str = VOLUME
    history_days: int = HISTORY_DAYS
    seed: int = RANDOM_SEED
    terminals: tuple[Terminal, ...] = field(default_factory=lambda: TERMINALS)


DEFAULT = BuildConfig()
