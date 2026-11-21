"""Self-consistency check on real data: does snapping undo a known perturbation?

We displace the input surface along its normals by a smooth random field (a few
voxels, like the drift of an approximate label), snap both the original and the
displaced surface, and measure how far apart the two results end up. A snapper that
truly locks onto the CT signal brings both to the same place; one that just follows
its input leaves the full perturbation in place.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from .geometry import frames
from .snap import SnapConfig, snap
from .tifxyz import TifXYZ


def perturb(surf: TifXYZ, rms: float, corr: float, seed: int = 0, scale: float = 1.0):
    """Return (displaced surface, displacement field in voxels along the normal)."""
    rng = np.random.default_rng(seed)
    field = gaussian_filter(rng.standard_normal(surf.shape), corr, mode="reflect")
    field *= rms / field.std()
    valid = surf.valid
    _, _, n, ok = frames(surf.zyx.astype(np.float64) * scale, valid)
    field = np.where(ok, field, 0.0)
    new = surf.zyx.astype(np.float64) + np.where(ok[..., None], n, 0.0) * field[..., None] / scale
    out = TifXYZ(
        x=np.where(valid, new[..., 2], -1).astype(np.float32),
        y=np.where(valid, new[..., 1], -1).astype(np.float32),
        z=np.where(valid, new[..., 0], -1).astype(np.float32),
        meta=dict(surf.meta),
    )
    return out, field


def perturbation_recovery(surf: TifXYZ, volume, cfg: SnapConfig, rms: float = 2.5, corr: float = 6.0, seed: int = 0, base=None):
    base = base or snap(surf, volume, cfg)
    cfg = SnapConfig(**base.config)  # reuse the resolved target for the displaced run
    moved, field = perturb(surf, rms, corr, seed, cfg.scale)
    res = snap(moved, volume, cfg)
    # signed distance between the two snapped surfaces, measured along the original normal
    d = (res.surface.zyx.astype(np.float64) - base.surface.zyx.astype(np.float64)) * cfg.scale
    resid = (d * base.normals).sum(-1)
    m = np.isfinite(base.offset) & np.isfinite(res.offset) & np.isfinite(resid)
    r, f = resid[m], field[m]
    if not m.any():
        keys = (
            "perturbation_rms_vox",
            "perturbation_max_vox",
            "residual_rms_vox",
            "residual_median_abs_vox",
            "within_1_vox",
            "within_2_vox",
            "recovered_fraction",
        )
        return {"vertices": 0, **{k: None for k in keys}}, resid, field
    return (
        {
            "vertices": int(m.sum()),
            "perturbation_rms_vox": float(np.sqrt((f**2).mean())),
            "perturbation_max_vox": float(np.abs(f).max()),
            "residual_rms_vox": float(np.sqrt((r**2).mean())),
            "residual_median_abs_vox": float(np.median(np.abs(r))),
            "within_1_vox": float((np.abs(r) <= 1).mean()),
            "within_2_vox": float((np.abs(r) <= 2).mean()),
            "recovered_fraction": float(1 - (r**2).mean() / (f**2).mean()),
        },
        resid,
        field,
    )
