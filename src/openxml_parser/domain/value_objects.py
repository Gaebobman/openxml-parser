from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    """Normalized bounding box in slide coordinates (0..1)."""

    x: float
    y: float
    width: float
    height: float

