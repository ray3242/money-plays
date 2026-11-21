"""QA renders: straightened cross-sections and flattened surface textures, before vs after."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .geometry import frames
from .tifxyz import TifXYZ


def _row_run(ok_row: np.ndarray, max_len: int):
    """Longest run of consecutive valid vertices in a grid row, capped at max_len."""
    best = (0, 0)
    start = None
    for i, v in enumerate(np.append(ok_row, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    a, b = best
    return a, min(b, a + max_len)


def straightened_section(surf: TifXYZ, volume, row: int, c0: int, c1: int, half: int = 40, scale: float = 1.0, frame=None):
    """CT resampled along grid row ``row`` so the input surface becomes the horizontal mid-line.

    Returns (image [2*half+1, n], t) where t are fractional column positions.
    """
    pts = surf.zyx.astype(np.float64) * scale
    _, _, n, _ = frame if frame is not None else frames(pts, surf.valid)
    seg = np.linalg.norm(np.diff(pts[row, c0:c1], axis=0), axis=1)
    per_cell = max(round(np.nanmedian(seg)), 1)
    t = np.arange(c0, c1 - 1, 1.0 / per_cell)
    i = np.floor(t).astype(int)
    f = (t - i)[:, None]
    p = pts[row, i] * (1 - f) + pts[row, i + 1] * f
    nn = n[row, i] * (1 - f) + n[row, i + 1] * f
    nn /= np.linalg.norm(nn, axis=1, keepdims=True)
    offs = np.arange(-half, half + 1)
    img = np.zeros((len(offs), len(t)), np.float32)
    for k in range(0, len(t), 256):
        sl = slice(k, k + 256)
        img[:, sl] = volume.sample(p[sl][:, None, :] + nn[sl][:, None, :] * offs[None, :, None]).T
    return img, t


def section_figure(
    surf: TifXYZ, offset: np.ndarray, volume, path, rows=None, n_rows: int = 4, max_cols: int = 120, half: int = 40, scale: float = 1.0, title: str = ""
):
    """Before/after cross-sections: red = input surface, cyan = snapped surface."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = frames(surf.zyx.astype(np.float64) * scale, surf.valid)
    ok = frame[3] & np.isfinite(offset)
    if rows is None:
        counts = ok.sum(1)
        cand = np.where(counts >= 0.5 * counts.max())[0]
        rows = cand[np.linspace(0, len(cand) - 1, n_rows + 2).astype(int)[1:-1]]
    fig, axes = plt.subplots(len(rows), 1, figsize=(18, 3.4 * len(rows)), squeeze=False)
    for ax, row in zip(axes[:, 0], rows):
        c0, c1 = _row_run(ok[row], max_cols)
        if c1 - c0 < 3:
            ax.set_axis_off()
            continue
        img, t = straightened_section(surf, volume, int(row), c0, c1, half, scale, frame)
        i = np.floor(t).astype(int)
        f = t - i
        o = offset[row, i] * (1 - f) + offset[row, i + 1] * f
        ax.imshow(img, cmap="gray", aspect="auto", extent=[c0, c1 - 1, half, -half], vmin=0, vmax=np.percentile(img, 99.5))
        ax.axhline(0, color="#ff3030", lw=1.0, label="input surface")
        ax.plot(t, o, color="#00e5ff", lw=1.0, label="snapped surface")
        ax.set_ylabel("offset along normal (voxels)")
        ax.set_xlabel(f"grid column (row {int(row)})")
        ax.legend(loc="upper right", fontsize=8, framealpha=0.6)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)
    return [int(r) for r in rows]


def render_texture(surf: TifXYZ, volume, window, upsample: int | None = None, layers=(0,), scale: float = 1.0, composite: str = "mean"):
    """Flattened texture of the grid window (r0, r1, c0, c1), sampled at ``upsample`` px per cell.

    ``layers`` are offsets along the normal (voxels) that get composited.
    """
    from scipy.ndimage import map_coordinates

    r0, r1, c0, c1 = window
    pts = surf.zyx.astype(np.float64) * scale
    valid = surf.valid
    _, _, n, ok = frames(pts, valid)
    if upsample is None:
        step = np.linalg.norm(np.diff(pts[r0:r1, c0:c1], axis=1), axis=-1)
        upsample = max(round(np.nanmedian(step)), 1)
    rr = np.arange(r0, r1 - 1, 1.0 / upsample)
    cc = np.arange(c0, c1 - 1, 1.0 / upsample)
    out = np.zeros((len(rr), len(cc)), np.float32)
    okf = ok.astype(np.float32)
    p0 = np.where(ok[..., None], pts, 0.0)
    n0 = np.where(ok[..., None], n, 0.0)
    band = 128
    for b in range(0, len(rr), band):
        gr, gc = np.meshgrid(rr[b : b + band], cc, indexing="ij")
        w = map_coordinates(okf, [gr, gc], order=1)
        good = w > 0.999
        if not good.any():
            continue
        p = np.stack([map_coordinates(p0[..., k], [gr, gc], order=1) for k in range(3)], -1)
        nn = np.stack([map_coordinates(n0[..., k], [gr, gc], order=1) for k in range(3)], -1)
        nn /= np.maximum(np.linalg.norm(nn, axis=-1, keepdims=True), 1e-9)
        acc = None
        for chunk in range(0, p.shape[1], 512):
            sl = (slice(None), slice(chunk, chunk + 512))
            g = good[sl]
            if not g.any():
                continue
            vals = np.stack([volume.sample(np.where(g[..., None], p[sl] + nn[sl] * o, np.nan)) for o in layers], 0)
            vals = vals.max(0) if composite == "max" else vals.mean(0)
            out[b : b + band, chunk : chunk + 512] = np.where(g, vals, 0)
        del acc
    return out


def save_gray(path, img, vmax=None):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vmax = vmax or float(np.percentile(img[img > 0], 99.5)) if (img > 0).any() else 1.0
    plt.imsave(Path(path), np.clip(img / vmax, 0, 1), cmap="gray", vmin=0, vmax=1)


def offset_figure(offset: np.ndarray, confidence: np.ndarray, path, search: float):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(3, 1, figsize=(16, 13), gridspec_kw={"height_ratios": [3, 3, 2]})
    im = ax[0].imshow(offset, cmap="RdBu_r", vmin=-search, vmax=search, interpolation="nearest")
    ax[0].set_title("applied offset along the normal (voxels)")
    fig.colorbar(im, ax=ax[0], fraction=0.02)
    im = ax[1].imshow(np.where(np.isfinite(offset), confidence, np.nan), cmap="viridis", vmin=0, vmax=1, interpolation="nearest")
    ax[1].set_title("confidence (0 = ambiguous, 1 = unique minimum)")
    fig.colorbar(im, ax=ax[1], fraction=0.02)
    o = offset[np.isfinite(offset)]
    ax[2].hist(o, bins=np.arange(-search, search + 0.25, 0.25), color="#4477aa")
    ax[2].set_xlabel("offset (voxels)")
    ax[2].set_ylabel("vertices")
    ax[2].set_title(f"median {np.median(o):+.2f}, mean |offset| {np.abs(o).mean():.2f}, 95th pct |offset| {np.percentile(np.abs(o), 95):.2f}")
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)
