"""Before/after numbers computed from the sampled CT profiles."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def _at(prof_like: np.ndarray, offs: np.ndarray, off: np.ndarray) -> np.ndarray:
    """Linear interpolation of per-vertex profiles at per-vertex offsets."""
    step = offs[1] - offs[0]
    pos = np.clip((off - offs[0]) / step, 0, len(offs) - 1.001)
    i = np.floor(pos).astype(int)
    f = pos - i
    a = np.take_along_axis(prof_like, i[..., None], -1)[..., 0]
    b = np.take_along_axis(prof_like, (i + 1)[..., None], -1)[..., 0]
    return a * (1 - f) + b * f


def surface_metrics(prof: np.ndarray, offs: np.ndarray, offset: np.ndarray, sigma: float = 2.0) -> dict:
    """How well does the surface sit on a sheet face before (offset 0) and after (offset)?

    * edge_strength: |d intensity / d normal| on the surface (grey levels per voxel)
    * dist_to_edge: distance from the surface to the nearest strong edge of the profile
    """
    m = np.isfinite(offset) & (prof.max(-1) > 0)
    p = prof[m]
    step = offs[1] - offs[0]
    sm = gaussian_filter1d(p, sigma / step, axis=-1, mode="nearest")
    g = np.abs(np.gradient(sm, step, axis=-1))
    zero = np.zeros(m.sum())
    off = offset[m]
    out = {}
    for name, o in (("before", zero), ("after", off)):
        out[name] = {
            "edge_strength_mean": float(_at(g, offs, o).mean()),
            "intensity_mean": float(_at(sm, offs, o).mean()),
        }
    out["offset"] = {
        "median": float(np.median(off)),
        "mean_abs": float(np.abs(off).mean()),
        "p95_abs": float(np.percentile(np.abs(off), 95)),
        "moved_more_than_1_vox": float((np.abs(off) > 1).mean()),
        "moved_more_than_2_vox": float((np.abs(off) > 2).mean()),
    }
    out["vertices"] = int(m.sum())
    return out
