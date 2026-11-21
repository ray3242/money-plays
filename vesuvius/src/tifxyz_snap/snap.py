"""Snap a tifxyz surface onto the papyrus sheet seen in the raw CT."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

from .geometry import frames, nan_gaussian
from .mrf import aggregate, argmin_subpixel
from .tifxyz import TifXYZ


@dataclass
class SnapConfig:
    search: float = 8.0  # max displacement along the normal, in voxels (each side)
    step: float = 0.5  # offset sampling step, voxels
    # "edge+" / "edge-": the sheet face (papyrus on the -normal / +normal side); "edge": pick the
    # sign the input surface already sits on; "center": the sheet mid-line (brightest ridge)
    target: str = "edge"
    sigma: float = 2.0  # Gaussian sigma along the normal (voxels) used for the cost
    patch: int = 2  # tangent-plane averaging: (2*patch+1)^2 rays per vertex
    patch_spacing: float = 3.0  # spacing between those rays, voxels
    lateral: float = 1.0  # Gaussian sigma (grid cells) pooling the cost across neighbouring vertices
    smooth_lambda: float = 0.3  # smoothness cost per offset step between neighbours
    smooth_trunc: float = 3.0  # cap of the smoothness cost (allows real discontinuities)
    post_sigma: float = 1.0  # final confidence-weighted smoothing of the offset field (grid cells)
    normal_smooth: float = 1.5  # smoothing of the grid before computing normals (grid cells)
    tile: int = 16  # vertices per tile side when sampling the volume
    iterations: int = 2  # re-sample around the snapped surface and snap again (removes smoothing bias)
    scale: float = 1.0  # multiply mesh coords by this to get voxels of the chosen level


@dataclass
class SnapResult:
    surface: TifXYZ
    offset: np.ndarray  # (H, W) signed displacement along the normal, voxels; NaN where invalid
    confidence: np.ndarray  # (H, W) in [0, 1]
    profiles: np.ndarray  # (H, W, D) patch-averaged CT intensity along the normal
    offsets_axis: np.ndarray  # (D,) offsets in voxels
    normals: np.ndarray  # (H, W, 3) in (z, y, x)
    config: dict


def sample_profiles(surf: TifXYZ, volume, cfg: SnapConfig, extra: float = 0.0, progress=None):
    """Patch-averaged intensity profiles along the normal for every valid vertex."""
    valid = surf.valid
    pts = surf.zyx.astype(np.float64) * cfg.scale
    tu, tv, n, ok = frames(pts, valid, cfg.normal_smooth)
    n_reach = int(np.floor(cfg.search / cfg.step + 1e-9)) + int(np.ceil(extra / cfg.step - 1e-9))
    offs = np.arange(-n_reach, n_reach + 1) * cfg.step
    h, w = valid.shape
    prof = np.zeros((h, w, len(offs)), dtype=np.float32)
    k = np.arange(-cfg.patch, cfg.patch + 1) * cfg.patch_spacing
    ka, kb = np.meshgrid(k, k, indexing="ij")
    ka, kb = ka.ravel(), kb.ravel()
    tiles = [(r, c) for r in range(0, h, cfg.tile) for c in range(0, w, cfg.tile)]
    for ti, (r, c) in enumerate(tiles):
        sl = (slice(r, r + cfg.tile), slice(c, c + cfg.tile))
        m = ok[sl]
        if m.any():
            base = pts[sl][m]  # (N, 3)
            rays = base[:, None, :] + tu[sl][m][:, None, :] * ka[None, :, None] + tv[sl][m][:, None, :] * kb[None, :, None]
            samp = rays[:, :, None, :] + n[sl][m][:, None, None, :] * offs[None, None, :, None]
            vals = volume.sample(samp).mean(1)  # (N, D)
            block = prof[sl]
            block[m] = vals
        if progress is not None:
            progress(ti + 1, len(tiles))
    return prof, offs, n, ok


def detect_edge_sign(prof: np.ndarray, offs: np.ndarray, ok: np.ndarray, cfg: SnapConfig) -> str:
    """Which sheet face is the input surface sitting on? Uses the mean profile slope at offset 0."""
    step = offs[1] - offs[0]
    if not ok.any():
        return "edge+"
    mean = gaussian_filter1d(prof[ok].mean(0), cfg.sigma / step, mode="nearest")
    i0 = int(np.argmin(np.abs(offs)))
    return "edge+" if np.gradient(mean)[i0] <= 0 else "edge-"


def profile_cost(prof: np.ndarray, offs: np.ndarray, cfg: SnapConfig, ok: np.ndarray | None = None) -> np.ndarray:
    """Per-vertex cost in [0, 1] for every candidate offset (lower = more sheet-like)."""
    step = offs[1] - offs[0]
    sm = gaussian_filter1d(prof, cfg.sigma / step, axis=-1, mode="nearest")
    if cfg.lateral > 0 and ok is not None:
        w = ok.astype(np.float32)
        num = gaussian_filter(sm * w[..., None], (cfg.lateral, cfg.lateral, 0), mode="nearest")
        den = gaussian_filter(w, cfg.lateral, mode="nearest")
        sm = num / np.maximum(den, 1e-3)[..., None]
    if cfg.target == "center":
        score = sm
    elif cfg.target in ("edge+", "edge-"):
        grad = np.gradient(sm, axis=-1)
        # edge+: papyrus on the -normal side, air on the +normal side (intensity falls along +n)
        score = -grad if cfg.target == "edge+" else grad
    else:
        raise ValueError(f"unknown target {cfg.target!r}")
    lo = score.min(-1, keepdims=True)
    hi = score.max(-1, keepdims=True)
    rng = hi - lo
    cost = np.where(rng > 1e-6, (hi - score) / np.maximum(rng, 1e-6), 0.5)
    return cost.astype(np.float32)


def solve(prof: np.ndarray, offs_full: np.ndarray, ok: np.ndarray, cfg: SnapConfig):
    """Offsets (voxels, NaN where inactive) and confidence from sampled profiles."""
    has_signal = prof.max(-1) > 0  # rays in masked / unscanned space stay put
    active = ok & has_signal
    cost_full = profile_cost(prof, offs_full, cfg, active)
    keep = np.abs(offs_full) <= cfg.search + 1e-6
    total = aggregate(cost_full[..., keep], active, cfg.smooth_lambda, cfg.smooth_trunc)
    idx, conf = argmin_subpixel(total)
    offs = offs_full[keep]
    flat = (total.max(-1) - total.min(-1)) <= 1e-6  # no edge anywhere in range: stay put
    idx = np.where(flat, float(np.argmin(np.abs(offs))), idx)
    conf = np.where(flat, 0.0, conf)
    off = np.where(active, offs[0] + idx * cfg.step, np.nan)
    conf = np.where(active, conf, 0.0).astype(np.float32)
    if cfg.post_sigma > 0:
        off = nan_gaussian(off, cfg.post_sigma, weights=conf + 0.05)
    return off, conf, active


def _snap_once(surf: TifXYZ, volume, cfg: SnapConfig, progress=None):
    margin = 3 * cfg.sigma
    prof, offs_full, n, ok = sample_profiles(surf, volume, cfg, extra=margin, progress=progress)
    if cfg.target == "edge":
        cfg = replace(cfg, target=detect_edge_sign(prof, offs_full, ok & (prof.max(-1) > 0), cfg))
    off, conf, active = solve(prof, offs_full, ok, cfg)
    off_apply = np.where(np.isfinite(off), off, 0.0)
    new = surf.zyx.astype(np.float64) * cfg.scale + np.where(active[..., None], n, 0.0) * off_apply[..., None]
    new /= cfg.scale
    valid = surf.valid
    out = TifXYZ(
        x=np.where(valid, new[..., 2], -1).astype(np.float32),
        y=np.where(valid, new[..., 1], -1).astype(np.float32),
        z=np.where(valid, new[..., 0], -1).astype(np.float32),
        meta=dict(surf.meta),
    )
    return out, off, conf, prof, offs_full, n, cfg


def snap(surf: TifXYZ, volume, cfg: SnapConfig | None = None, progress=None) -> SnapResult:
    """Snap ``surf`` onto the sheet. The total move per vertex is limited to ``cfg.search`` voxels."""
    cfg = cfg or SnapConfig()
    out, off, conf, prof, offs_full, n, cfg = _snap_once(surf, volume, cfg, progress)
    for _ in range(max(cfg.iterations, 1) - 1):
        nxt, _, conf_i, *_ = _snap_once(out, volume, cfg, progress)
        # total displacement measured along the original normal, clamped to the search range
        d = (nxt.zyx.astype(np.float64) - surf.zyx.astype(np.float64)) * cfg.scale
        tot = np.clip((d * np.nan_to_num(n)).sum(-1), -cfg.search, cfg.search)
        off = np.where(np.isfinite(off), tot, np.nan)
        conf = np.minimum(conf, conf_i)
        new = surf.zyx.astype(np.float64) + np.nan_to_num(n) * np.nan_to_num(off)[..., None] / cfg.scale
        valid = surf.valid
        out = TifXYZ(
            x=np.where(valid, new[..., 2], -1).astype(np.float32),
            y=np.where(valid, new[..., 1], -1).astype(np.float32),
            z=np.where(valid, new[..., 0], -1).astype(np.float32),
            meta=dict(surf.meta),
        )
    return SnapResult(out, off, conf, prof, offs_full, n, asdict(cfg))
