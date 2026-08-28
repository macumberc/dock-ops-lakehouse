"""Procedural synthetic dock-camera image generator.

Renders small, labeled dock-door camera frames in four states so a computer-vision
classifier has something real to learn from — without any real footage. Each state
has a distinct visual composition (with per-image lighting/noise jitter so the task
is learnable but not trivial):

    empty       - open bay, dark doorway, visible back wall
    docked      - trailer back fills the doorway, no activity
    loading     - trailer + pallets + forklift + worker figure
    obstructed  - pallets/barrier stacked in front of the bay

Filenames encode the ground truth so downstream ingest can parse it:
    {TERMINAL}_{DOCK}_{YYYYMMDDHHMM}_{LABEL}.png

All data is synthetic. No real customer imagery is used.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from dock_ops.config import DOCK_STATES, TERMINALS, RANDOM_SEED, REFERENCE_DATE, Terminal

IMG_W, IMG_H = 192, 144

# Realistic mix of dock states across a camera's day.
_STATE_P = {"empty": 0.34, "docked": 0.24, "loading": 0.30, "obstructed": 0.12}


def _bg(draw: ImageDraw.ImageDraw, rng: np.random.RandomState) -> None:
    """Paint the warehouse interior: floor, walls, and the dock doorway frame."""
    light = int(rng.randint(120, 175))
    # Back wall
    draw.rectangle([0, 0, IMG_W, IMG_H], fill=(light, light, light + 5))
    # Floor (lower third), slightly darker
    floor = int(light * 0.7)
    draw.rectangle([0, int(IMG_H * 0.68), IMG_W, IMG_H], fill=(floor, floor, floor))
    # Painted safety line
    draw.line([0, int(IMG_H * 0.68), IMG_W, int(IMG_H * 0.68)], fill=(210, 190, 40), width=2)


def _doorway() -> tuple[int, int, int, int]:
    """Return the bay doorway rectangle (x0, y0, x1, y1)."""
    return int(IMG_W * 0.22), int(IMG_H * 0.12), int(IMG_W * 0.78), int(IMG_H * 0.72)


def _render(label: str, rng: np.random.RandomState) -> Image.Image:
    """Render a single dock frame for the given ground-truth label."""
    img = Image.new("RGB", (IMG_W, IMG_H))
    d = ImageDraw.Draw(img)
    _bg(d, rng)
    x0, y0, x1, y1 = _doorway()

    if label == "empty":
        # Dark open doorway showing outside daylight at the top.
        d.rectangle([x0, y0, x1, y1], fill=(40, 40, 48))
        d.rectangle([x0, y0, x1, y0 + int((y1 - y0) * 0.18)], fill=(150, 170, 200))
    elif label == "docked":
        # Trailer back panel fills the doorway; two closed doors + hinges.
        d.rectangle([x0, y0, x1, y1], fill=(200, 205, 210))
        mid = (x0 + x1) // 2
        d.line([mid, y0, mid, y1], fill=(120, 120, 125), width=3)
        for yy in np.linspace(y0 + 8, y1 - 8, 4):
            d.line([x0 + 4, int(yy), x0 + 12, int(yy)], fill=(90, 90, 95), width=2)
            d.line([x1 - 12, int(yy), x1 - 4, int(yy)], fill=(90, 90, 95), width=2)
    elif label == "loading":
        # Open trailer (dark interior) + pallets on the floor + forklift + worker.
        d.rectangle([x0, y0, x1, y1], fill=(60, 55, 50))
        # Pallets (stacked boxes) spilling out of the bay
        for _ in range(int(rng.randint(3, 6))):
            px = int(rng.randint(x0, x1 - 30))
            py = int(rng.randint(int(IMG_H * 0.55), int(IMG_H * 0.8)))
            c = int(rng.randint(150, 205))
            d.rectangle([px, py, px + 26, py + 20], fill=(c, int(c * 0.8), 60))
        # Forklift (orange body + mast)
        fx = int(rng.randint(x0 + 5, x1 - 45))
        fy = int(IMG_H * 0.72)
        d.rectangle([fx, fy - 22, fx + 34, fy], fill=(230, 130, 20))
        d.line([fx + 30, fy - 30, fx + 30, fy], fill=(60, 60, 60), width=3)
        d.ellipse([fx + 2, fy - 6, fx + 12, fy + 4], fill=(30, 30, 30))
        d.ellipse([fx + 22, fy - 6, fx + 32, fy + 4], fill=(30, 30, 30))
        # Worker (high-vis vest)
        wx = int(rng.randint(x0 + 5, x1 - 15))
        wy = int(IMG_H * 0.60)
        d.ellipse([wx, wy, wx + 8, wy + 8], fill=(240, 220, 180))       # head
        d.rectangle([wx - 2, wy + 8, wx + 10, wy + 26], fill=(240, 210, 30))  # vest
    elif label == "obstructed":
        # Bay blocked: barrier + stacked pallets in the foreground.
        d.rectangle([x0, y0, x1, y1], fill=(70, 70, 78))
        for i in range(int(rng.randint(4, 7))):
            bx = x0 + 4 + i * 22
            by = int(IMG_H * 0.42) + int(rng.randint(-6, 6))
            d.rectangle([bx, by, bx + 20, by + 42], fill=(150, 110, 60))
        # Red/white barrier bar
        by = int(IMG_H * 0.40)
        for i in range(0, IMG_W, 20):
            col = (200, 40, 40) if (i // 20) % 2 == 0 else (235, 235, 235)
            d.rectangle([i, by, i + 20, by + 8], fill=col)

    # Lighting + sensor noise jitter so classes aren't trivially separable
    # (keeps the task realistic — a real camera model lands in the high 90s,
    # not a suspicious perfect score).
    arr = np.asarray(img).astype(np.float32)
    arr += rng.normal(0, 30, arr.shape)          # per-pixel gaussian sensor noise
    arr += rng.randint(-28, 29)                   # global exposure shift
    # occasional low-contrast / glare frames
    if rng.random() < 0.15:
        arr = arr * float(rng.uniform(0.55, 0.8)) + float(rng.randint(20, 60))
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def generate_images(
    target_dir: str,
    terminals: tuple[Terminal, ...] = TERMINALS,
    images_per_door: int = 16,
    seed: int = RANDOM_SEED,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """Generate labeled dock-camera images for every door across all terminals.

    Args:
        target_dir: destination directory (local or /Volumes path).
        terminals: terminals to simulate.
        images_per_door: snapshots per dock door.
        seed: RNG seed for deterministic output.
        end_date: reference date for image timestamps.

    Returns:
        Summary dict with per-label counts for evidence.
    """
    os.makedirs(target_dir, exist_ok=True)
    rng = np.random.RandomState(seed + 7)
    if end_date is None:
        end_date = REFERENCE_DATE.replace(minute=0, second=0, microsecond=0)

    labels = list(DOCK_STATES)
    probs = np.array([_STATE_P[s] for s in labels])
    probs = probs / probs.sum()

    counts: dict[str, int] = {s: 0 for s in labels}
    total = 0
    for term in terminals:
        for door in range(1, term.doors + 1):
            dock_id = f"{term.code}-D{door:02d}"
            for k in range(images_per_door):
                label = str(rng.choice(labels, p=probs))
                ts = end_date - timedelta(hours=int(rng.randint(0, 24 * 30)))
                fname = f"{term.code}_{dock_id}_{ts:%Y%m%d%H%M}_{label}.png"
                _render(label, rng).save(os.path.join(target_dir, fname))
                counts[label] += 1
                total += 1

    return {"images": total, "by_label": counts, "target_dir": target_dir, "size": [IMG_W, IMG_H]}
