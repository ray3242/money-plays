"""Command line interface: tifxyz-snap {snap,validate,render}."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import fields
from pathlib import Path

import numpy as np
import tifffile

from . import __version__
from .snap import SnapConfig, snap
from .tifxyz import read_tifxyz, write_tifxyz
from .volume import ZarrVolume


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("tifxyz", help="input tifxyz directory (x.tif, y.tif, z.tif, meta.json)")
    p.add_argument("volume", help="Zarr v2 / OME-Zarr volume: local path or http(s) URL")
    p.add_argument("--level", default="0", help="resolution level inside the zarr (default 0)")
    p.add_argument("--scale", type=float, default=None, help="mesh coordinate -> voxel factor (default 1 / 2**level)")
    p.add_argument("--cache", default="~/.cache/tifxyz-snap", help="chunk cache for remote volumes")
    d = SnapConfig()
    p.add_argument("--search", type=float, default=d.search, help="max move along the normal, voxels [%(default)s]")
    p.add_argument("--step", type=float, default=d.step, help="offset sampling step, voxels [%(default)s]")
    p.add_argument(
        "--target", choices=["edge", "edge+", "edge-", "center"], default=d.target, help="sheet face (edge, auto sign) or sheet mid-line (center) [%(default)s]"
    )
    p.add_argument("--sigma", type=float, default=d.sigma, help="smoothing along the normal, voxels [%(default)s]")
    p.add_argument("--lateral", type=float, default=d.lateral, help="cost pooling across neighbours, grid cells [%(default)s]")
    p.add_argument("--smooth-lambda", type=float, default=d.smooth_lambda, help="smoothness weight [%(default)s]")
    p.add_argument("--smooth-trunc", type=float, default=d.smooth_trunc, help="smoothness cap [%(default)s]")
    p.add_argument("--post-sigma", type=float, default=d.post_sigma, help="final smoothing of the offset field, grid cells [%(default)s]")
    p.add_argument("--iterations", type=int, default=d.iterations, help="snap passes [%(default)s]")
    p.add_argument("--patch", type=int, default=d.patch, help="rays per vertex = (2*patch+1)^2 [%(default)s]")
    p.add_argument("--patch-spacing", type=float, default=d.patch_spacing, help="ray spacing, voxels [%(default)s]")


def _config(args) -> SnapConfig:
    level = int(args.level) if str(args.level).isdigit() else 0
    scale = args.scale if args.scale is not None else 1.0 / (2**level)
    names = {f.name for f in fields(SnapConfig)}
    kw = {k: v for k, v in vars(args).items() if k in names and v is not None}
    kw["scale"] = scale
    return SnapConfig(**kw)


def _volume(args) -> ZarrVolume:
    return ZarrVolume(args.volume, args.level, cache_dir=Path(args.cache).expanduser())


def _progress(label: str):
    t0 = time.time()

    def cb(i, n):
        if i == n or i % max(n // 20, 1) == 0:
            print(f"\r{label}: {100 * i // n:3d}%  ({time.time() - t0:.0f}s)", end="" if i < n else "\n", file=sys.stderr, flush=True)

    return cb


def cmd_snap(args) -> int:
    from .metrics import surface_metrics

    surf = read_tifxyz(args.tifxyz)
    vol = _volume(args)
    cfg = _config(args)
    out = Path(args.output)
    t0 = time.time()
    res = snap(surf, vol, cfg, progress=_progress("sampling CT along normals"))
    if args.min_confidence > 0:
        low = res.confidence < args.min_confidence
        pts = np.where(low[..., None], surf.xyz, res.surface.xyz)
        res.surface.x, res.surface.y, res.surface.z = (pts[..., k].astype(np.float32) for k in range(3))
        res.offset = np.where(low & np.isfinite(res.offset), 0.0, res.offset)
    write_tifxyz(
        out,
        res.surface,
        extra_meta={"tifxyz_snap": {"version": __version__, "source": str(args.tifxyz), "volume": args.volume, "level": str(args.level), **res.config}},
    )
    tifffile.imwrite(out / "snap_offset.tif", np.nan_to_num(res.offset, nan=0.0).astype(np.float32))
    tifffile.imwrite(out / "snap_confidence.tif", res.confidence.astype(np.float32))
    report = surface_metrics(res.profiles, res.offsets_axis, res.offset, cfg.sigma)
    report["config"] = res.config
    report["seconds"] = round(time.time() - t0, 1)
    report["downloaded_gb"] = round(vol.fetched_bytes / 1e9, 3)
    if not args.no_qa:
        from .render import offset_figure, section_figure

        qa = out / "qa"
        qa.mkdir(exist_ok=True)
        offset_figure(res.offset, res.confidence, qa / "offset_map.png", cfg.search)
        report["section_rows"] = section_figure(surf, res.offset, vol, qa / "sections.png", scale=cfg.scale)
    (out / "snap_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("vertices", "before", "after", "offset", "seconds")}, indent=2))
    print(f"wrote {out}")
    return 0


def cmd_validate(args) -> int:
    from .validate import perturbation_recovery

    surf = read_tifxyz(args.tifxyz)
    vol = _volume(args)
    cfg = _config(args)
    base = snap(surf, vol, cfg, progress=_progress("snapping input"))
    rows = []
    for rms in args.rms:
        m, _, _ = perturbation_recovery(surf, vol, cfg, rms=rms, corr=args.corr, seed=args.seed, base=base)
        rows.append(m)
        print(json.dumps({k: v if v is None else round(v, 3) for k, v in m.items()}))
    if args.output:
        Path(args.output).write_text(json.dumps({"config": base.config, "results": rows}, indent=2))
    return 0


def cmd_render(args) -> int:
    from .render import render_texture, save_gray

    surf = read_tifxyz(args.tifxyz)
    vol = _volume(args)
    cfg = _config(args)
    h, w = surf.shape
    window = tuple(args.window) if args.window else (0, h, 0, w)
    layers = np.arange(-args.half_thickness, args.half_thickness + 1e-6, 1.0) + args.layer_offset
    img = render_texture(surf, vol, window, upsample=args.upsample, layers=layers, scale=cfg.scale, composite=args.composite)
    if str(args.output).lower().endswith((".tif", ".tiff")):
        tifffile.imwrite(args.output, np.clip(img, 0, 255).astype(np.uint8))
    else:
        save_gray(args.output, img)
    print(f"wrote {args.output} {img.shape}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tifxyz-snap", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("snap", help="snap a tifxyz surface onto the papyrus sheet in the CT")
    _add_common(p)
    p.add_argument("-o", "--output", required=True, help="output tifxyz directory")
    p.add_argument("--min-confidence", type=float, default=0.0, help="leave vertices below this confidence where they were")
    p.add_argument("--no-qa", action="store_true", help="skip the QA figures")
    p.set_defaults(func=cmd_snap)

    p = sub.add_parser("validate", help="perturb the surface by a known amount and check the snap brings it back")
    _add_common(p)
    p.add_argument("--rms", type=float, nargs="+", default=[1.5, 2.5], help="perturbation RMS values, voxels")
    p.add_argument("--corr", type=float, default=6.0, help="perturbation correlation length, grid cells")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("-o", "--output", help="write results as JSON")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("render", help="render a flattened texture of a tifxyz surface (for before/after checks)")
    _add_common(p)
    p.add_argument("-o", "--output", required=True, help="output .png or .tif")
    p.add_argument("--window", type=int, nargs=4, metavar=("R0", "R1", "C0", "C1"), help="grid window to render")
    p.add_argument("--upsample", type=int, default=None, help="pixels per grid cell (default: one per voxel)")
    p.add_argument("--layer-offset", type=float, default=0.0, help="render this many voxels along the normal")
    p.add_argument("--half-thickness", type=float, default=0.0, help="composite layers within +- this many voxels")
    p.add_argument("--composite", choices=["mean", "max"], default="mean")
    p.set_defaults(func=cmd_render)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
