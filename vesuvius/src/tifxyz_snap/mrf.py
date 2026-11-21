"""Scanline (semi-global) optimisation of a per-vertex label field on a 2D grid.

Each vertex has a cost per candidate offset. We want the offset field that has low
cost but changes slowly between neighbouring vertices, so a noisy vertex cannot jump
onto the neighbouring papyrus wrap on its own. Costs are aggregated along the 8 grid
directions with a truncated-linear smoothness term, as in semi-global matching.
"""

from __future__ import annotations

import numpy as np


def _min_conv_truncated_linear(m: np.ndarray, lam: float, trunc: float) -> np.ndarray:
    """out[..., d] = min_d' m[..., d'] + min(lam * |d - d'|, trunc)."""
    out = m.copy()
    for d in range(1, out.shape[-1]):
        np.minimum(out[..., d], out[..., d - 1] + lam, out=out[..., d])
    for d in range(out.shape[-1] - 2, -1, -1):
        np.minimum(out[..., d], out[..., d + 1] + lam, out=out[..., d])
    np.minimum(out, m.min(-1, keepdims=True) + trunc, out=out)
    return out


def _lines(h: int, w: int, dy: int, dx: int):
    """Yield (ys, xs) index arrays of step t for all scanlines travelling along (dy, dx)."""
    ys, xs = np.mgrid[0:h, 0:w]
    if dx != 0:
        t = xs if dx > 0 else (w - 1 - xs)
    else:
        t = ys if dy > 0 else (h - 1 - ys)
    # predecessor of (y, x) is (y - dy, x - dx)
    order = np.argsort(t.ravel(), kind="stable")
    tt = t.ravel()[order]
    bounds = np.searchsorted(tt, np.arange(tt.max() + 2))
    for i in range(len(bounds) - 1):
        sel = order[bounds[i] : bounds[i + 1]]
        yield ys.ravel()[sel], xs.ravel()[sel]


def aggregate(cost: np.ndarray, valid: np.ndarray, lam: float, trunc: float, directions: int = 8) -> np.ndarray:
    """Aggregate ``cost`` (H, W, D) along 4 or 8 directions. Invalid vertices break paths."""
    h, w, _d = cost.shape
    cost = np.where(valid[..., None], cost, 0.0).astype(np.float32)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if directions == 8:
        dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    total = np.zeros_like(cost)
    for dy, dx in dirs:
        L = np.zeros_like(cost)
        for ys, xs in _lines(h, w, dy, dx):
            py, px = ys - dy, xs - dx
            inside = (py >= 0) & (py < h) & (px >= 0) & (px < w)
            cur = cost[ys, xs].copy()
            if inside.any():
                pv = inside.copy()
                pv[inside] = valid[py[inside], px[inside]]
                if pv.any():
                    prev = L[py[pv], px[pv]]
                    msg = _min_conv_truncated_linear(prev, lam, trunc)
                    msg -= prev.min(-1, keepdims=True)
                    cur[pv] += msg
            L[ys, xs] = cur
        total += L
    return total


def argmin_subpixel(total: np.ndarray):
    """Argmin over the last axis with parabolic sub-step refinement, plus a confidence.

    Confidence is the gap between the best cost and the best cost at least 3 labels away,
    normalised by the cost range of that vertex (0 = ambiguous, 1 = unique minimum).
    """
    d = total.shape[-1]
    i = total.argmin(-1)
    best = np.take_along_axis(total, i[..., None], -1)[..., 0]
    lo = np.take_along_axis(total, np.clip(i - 1, 0, d - 1)[..., None], -1)[..., 0]
    hi = np.take_along_axis(total, np.clip(i + 1, 0, d - 1)[..., None], -1)[..., 0]
    denom = lo - 2 * best + hi
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where((denom > 1e-9) & (i > 0) & (i < d - 1), 0.5 * (lo - hi) / denom, 0.0)
    frac = np.clip(frac, -0.5, 0.5)
    far = np.abs(np.arange(d)[None, None, :] - i[..., None]) >= 3
    second = np.where(far, total, np.inf).min(-1)
    rng = total.max(-1) - best
    with np.errstate(invalid="ignore", divide="ignore"):
        conf = np.where(rng > 1e-9, (second - best) / rng, 0.0)
    return i + frac, np.clip(conf, 0.0, 1.0).astype(np.float32)
