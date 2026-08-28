"""Synthetic dock telemetry generator for Meridian Freight Systems.

Emits an append-only *event stream* (the shape a yard-management + dock-sensor
system would land in cloud storage): per-visit gate and dock events. The stream
is engineered so the business story is visible in the data — inbound waves in the
morning, an outbound cutoff crunch in the afternoon, and a fixed-shift labor plan
that does not match either, producing detention and overtime.

All data is synthetic. No real customer data is used.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from dock_ops.config import TERMINALS, HISTORY_DAYS, RANDOM_SEED, Terminal

# Event types emitted per trailer visit, in causal order.
EVENT_TYPES = ("gate_in", "dock_assigned", "load_start", "load_end", "gate_out")

# Hourly arrival intensity weights (index = hour of day, 0-23).
# Inbound freight arrives in a morning wave; outbound builds toward the evening
# cutoff. Their sum is the door demand curve the fixed shift plan misses.
_INBOUND_WEIGHTS = np.array(
    [1, 1, 1, 2, 4, 7, 11, 13, 12, 9, 6, 4, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1],
    dtype=float,
)
_OUTBOUND_WEIGHTS = np.array(
    [1, 1, 1, 1, 1, 2, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15, 14, 11, 7, 4, 2, 1, 1],
    dtype=float,
)


def _pick_hour(rng: np.random.RandomState, weights: np.ndarray) -> int:
    """Sample an hour-of-day from an intensity weight curve."""
    p = weights / weights.sum()
    return int(rng.choice(np.arange(24), p=p))


def generate_events(
    terminals: tuple[Terminal, ...] = TERMINALS,
    history_days: int = HISTORY_DAYS,
    seed: int = RANDOM_SEED,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """Generate the full raw event stream across all terminals and days.

    Args:
        terminals: terminals to simulate.
        history_days: number of days of history to generate.
        seed: RNG seed for deterministic output.
        end_date: last day of the window (defaults to today, UTC midnight).

    Returns:
        A list of event records (dicts), one per gate/dock event.
    """
    rng = np.random.RandomState(seed)
    if end_date is None:
        end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=history_days - 1)

    events: list[dict[str, Any]] = []
    visit_counter = 0

    for day_offset in range(history_days):
        day = start_date + timedelta(days=day_offset)
        weekday = day.weekday()  # 0=Mon
        # Weekends run lighter volume.
        day_factor = 0.45 if weekday >= 5 else 1.0

        for term in terminals:
            # Daily trailer volume scales with door count. Tuned so the diurnal
            # waves push peak-hour door utilization high (docks slammed) while
            # nights stay quiet — the core imbalance this build addresses.
            base = term.doors * 10.0 * day_factor
            n_visits = max(1, int(rng.poisson(base)))

            for _ in range(n_visits):
                visit_counter += 1
                direction = "inbound" if rng.random() < 0.52 else "outbound"
                weights = _INBOUND_WEIGHTS if direction == "inbound" else _OUTBOUND_WEIGHTS
                hour = _pick_hour(rng, weights)
                minute = int(rng.randint(0, 60))
                gate_in = day + timedelta(hours=hour, minutes=minute)

                visit_id = f"V{gate_in:%Y%m%d}-{term.code}-{visit_counter:06d}"
                trailer_id = f"MFS-{rng.randint(10000, 99999)}"
                door_num = int(rng.randint(1, term.doors + 1))
                dock_id = f"{term.code}-D{door_num:02d}"
                worker_id = f"W{term.code}-{rng.randint(1, 61):03d}"
                freight_lbs = int(rng.normal(18000, 5000))
                freight_lbs = max(1500, freight_lbs)

                # Wait to be assigned a door. During peak hours doors are scarce,
                # so the wait balloons -> detention. Model peak congestion by the
                # demand weight at this hour.
                demand = (_INBOUND_WEIGHTS[hour] + _OUTBOUND_WEIGHTS[hour])
                congestion = demand / (_INBOUND_WEIGHTS + _OUTBOUND_WEIGHTS).max()
                wait_min = float(rng.gamma(shape=2.0, scale=8.0 + 55.0 * congestion))

                # Time on the door: assignment -> load start (spotting) -> load -> depart.
                spot_min = float(rng.uniform(4, 12))
                load_min = float(np.clip(rng.normal(58 + freight_lbs / 1000.0, 14), 20, 150))
                depart_min = float(rng.uniform(3, 10))

                dock_assigned = gate_in + timedelta(minutes=wait_min)
                load_start = dock_assigned + timedelta(minutes=spot_min)
                load_end = load_start + timedelta(minutes=load_min)
                gate_out = load_end + timedelta(minutes=depart_min)

                stamps = {
                    "gate_in": gate_in,
                    "dock_assigned": dock_assigned,
                    "load_start": load_start,
                    "load_end": load_end,
                    "gate_out": gate_out,
                }
                for etype, ts in stamps.items():
                    events.append(
                        {
                            "event_id": f"{visit_id}-{etype}",
                            "visit_id": visit_id,
                            "terminal": term.code,
                            "terminal_name": term.name,
                            "dock_id": dock_id if etype != "gate_in" else None,
                            "trailer_id": trailer_id,
                            "event_type": etype,
                            "event_ts": ts.isoformat(timespec="seconds"),
                            "direction": direction,
                            "freight_weight_lbs": freight_lbs,
                            "worker_id": worker_id if etype in ("load_start", "load_end") else None,
                        }
                    )

    events.sort(key=lambda e: e["event_ts"])
    return events


def write_events_to_dir(
    events: list[dict[str, Any]],
    target_dir: str,
    files_per_day: int = 1,
) -> dict[str, Any]:
    """Write events as newline-delimited JSON files, partitioned by date.

    Produces one (or more) files per event-date so an Auto Loader stream sees a
    realistic trickle of files. Works against a local path or a /Volumes path.

    Args:
        events: event records from :func:`generate_events`.
        target_dir: destination directory (created if missing).
        files_per_day: number of shard files to split each day's events into.

    Returns:
        A summary dict with counts for evidence.
    """
    os.makedirs(target_dir, exist_ok=True)
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        day = e["event_ts"][:10]
        by_day.setdefault(day, []).append(e)

    files_written = 0
    for day, recs in sorted(by_day.items()):
        shards = np.array_split(recs, max(1, files_per_day))
        for i, shard in enumerate(shards):
            if len(shard) == 0:
                continue
            path = os.path.join(target_dir, f"telemetry_{day}_{i:02d}.json")
            with open(path, "w") as f:
                for rec in shard:
                    f.write(json.dumps(rec) + "\n")
            files_written += 1

    return {
        "events": len(events),
        "days": len(by_day),
        "files_written": files_written,
        "target_dir": target_dir,
    }
