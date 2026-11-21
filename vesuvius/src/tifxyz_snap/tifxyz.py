"""Minimal tifxyz reader/writer (the quad-mesh format used by VC3D / villa)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import tifffile


@dataclass
class TifXYZ:
    """A tifxyz surface: three float32 grids holding x, y, z volume coordinates.

    Invalid vertices are stored as (-1, -1, -1) on disk; ``valid`` is the mask.
    """

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        return self.x.shape

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.z) & (self.z >= 0) & (self.x != -1)

    @property
    def xyz(self) -> np.ndarray:
        return np.stack([self.x, self.y, self.z], axis=-1)

    @property
    def zyx(self) -> np.ndarray:
        return np.stack([self.z, self.y, self.x], axis=-1)


def read_tifxyz(path: str | Path) -> TifXYZ:
    path = Path(path)
    grids = [tifffile.imread(path / f"{c}.tif").astype(np.float32) for c in "xyz"]
    if not (grids[0].shape == grids[1].shape == grids[2].shape) or grids[0].ndim != 2:
        raise ValueError(f"{path}: x/y/z.tif must be 2D grids of identical shape")
    meta_path = path / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return TifXYZ(*grids, meta=meta)


def write_tifxyz(path: str | Path, surf: TifXYZ, extra_meta: dict | None = None) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    valid = surf.valid
    meta = dict(surf.meta)
    for c, grid in zip("xyz", (surf.x, surf.y, surf.z)):
        out = np.where(valid, grid, -1.0).astype(np.float32)
        tifffile.imwrite(path / f"{c}.tif", out)
    if valid.any():
        pts = surf.xyz[valid]
        meta["bbox"] = [pts.min(0).astype(float).tolist(), pts.max(0).astype(float).tolist()]
    meta.setdefault("format", "tifxyz")
    meta.setdefault("type", "seg")
    if extra_meta:
        meta.update(extra_meta)
    (path / "meta.json").write_text(json.dumps(meta, indent=4))
