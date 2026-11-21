"""Grid geometry helpers: NaN-aware smoothing, tangents and normals of a tifxyz grid."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def nan_gaussian(a: np.ndarray, sigma: float, weights: np.ndarray | None = None) -> np.ndarray:
    """Gaussian filter over the two grid axes that ignores NaNs (normalised convolution)."""
    if sigma <= 0:
        return a.copy()
    valid = np.isfinite(a)
    w = valid.astype(np.float64) if weights is None else np.where(valid, weights, 0.0)
    sig = (sigma, sigma) + (0,) * (a.ndim - 2)
    num = gaussian_filter(np.where(valid, a, 0.0) * w, sig, mode="nearest")
    den = gaussian_filter(w, sig, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[~valid] = np.nan
    return out


def _nan_gradient(p: np.ndarray, axis: int) -> np.ndarray:
    """Central difference where both neighbours exist, one-sided otherwise."""
    p = np.moveaxis(p, axis, 0)
    fwd = np.full_like(p, np.nan)
    bwd = np.full_like(p, np.nan)
    fwd[:-1] = p[1:] - p[:-1]
    bwd[1:] = p[1:] - p[:-1]
    both = np.isfinite(fwd) & np.isfinite(bwd)
    g = np.where(both, 0.5 * (fwd + bwd), np.where(np.isfinite(fwd), fwd, bwd))
    return np.moveaxis(g, 0, axis)


def frames(points: np.ndarray, valid: np.ndarray, smooth: float = 1.5):
    """Per-vertex unit tangents (tu, tv) and unit normal n = tu x tv of a (H, W, 3) grid.

    Returns arrays of shape (H, W, 3); invalid vertices are NaN. ``ok`` marks
    vertices that have a usable frame.
    """
    p = points.astype(np.float64).copy()
    p[~valid] = np.nan
    ps = nan_gaussian(p, smooth)
    du = _nan_gradient(ps, 1)
    dv = _nan_gradient(ps, 0)
    n = np.cross(du, dv)
    with np.errstate(invalid="ignore", divide="ignore"):
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        tu = du / np.linalg.norm(du, axis=-1, keepdims=True)
    tv = np.cross(n, tu)
    ok = valid & np.isfinite(n).all(-1) & np.isfinite(tu).all(-1)
    for a in (n, tu, tv):
        a[~ok] = np.nan
    return tu, tv, n, ok
