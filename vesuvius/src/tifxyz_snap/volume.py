"""Lazy reader for (OME-)Zarr v2 volumes over HTTP(S) or local disk, with an on-disk chunk cache.

Only the chunks a surface actually touches are fetched, so a laptop can work on a
multi-terabyte scroll volume without downloading it.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

SAFE_CODECS = frozenset({"blosc", "zstd", "gzip", "zlib", "lz4", "bz2", "lzma"})


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


class ZarrVolume:
    """One resolution level of a Zarr v2 array, indexed (z, y, x)."""

    def __init__(
        self,
        root: str,
        level: int | str = 0,
        cache_dir: str | os.PathLike | None = None,
        mem_chunks: int = 512,
        workers: int = 16,
    ):
        self.root = str(root).rstrip("/")
        self.level = str(level)
        self.remote = _is_url(self.root)
        self.workers = workers
        self._session = None
        self._lock = threading.Lock()
        self._mem: OrderedDict[tuple[int, int, int], np.ndarray | None] = OrderedDict()
        self._mem_chunks = mem_chunks
        self.block = 256
        self.max_block_voxels = 512**3
        self.fetched_bytes = 0
        self.fetched_chunks = 0

        raw = self._read_bytes(f"{self.level}/.zarray")
        self.array_path = f"{self.level}/"
        if raw is None:
            raw = self._read_bytes(".zarray")  # standalone array, no pyramid levels
            self.array_path = ""
        if raw is None:
            raise FileNotFoundError(f"no .zarray at {self.root}/{self.level} or {self.root}")
        zarray = json.loads(raw)
        if zarray.get("zarr_format", 2) != 2:
            raise ValueError("only Zarr v2 arrays are supported")
        self.shape = tuple(zarray["shape"])
        self.chunks = tuple(zarray["chunks"])
        if len(self.shape) != 3:
            raise ValueError(f"expected a 3D array, got shape {self.shape}")
        self.dtype = np.dtype(zarray["dtype"])
        self.fill_value = zarray.get("fill_value") or 0
        self.sep = zarray.get("dimension_separator", ".")
        self.order = zarray.get("order", "C")
        if zarray.get("filters"):
            raise ValueError("Zarr filters are not supported")
        comp = zarray.get("compressor")
        self._codec = None
        if comp is not None:
            import numcodecs

            if comp.get("id") not in SAFE_CODECS:
                raise ValueError(f"unsupported Zarr compressor {comp.get('id')!r}; allowed: {sorted(SAFE_CODECS)}")
            self._codec = numcodecs.get_codec(comp)

        self.cache_dir = None
        if self.remote and cache_dir is not None:
            tag = hashlib.sha1(f"{self.root}/{self.level}".encode()).hexdigest()[:12]
            self.cache_dir = Path(cache_dir) / tag
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- raw IO -----------------------------------------------------------------
    def _get_session(self):
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            s = requests.Session()
            retry = Retry(total=5, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504))
            s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=64))
            s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=64))
            self._session = s
        return self._session

    def _read_bytes(self, rel: str) -> bytes | None:
        if self.remote:
            r = self._get_session().get(f"{self.root}/{rel}", timeout=120)
            if r.status_code in (403, 404):
                return None
            r.raise_for_status()
            return r.content
        p = Path(self.root) / rel
        return p.read_bytes() if p.exists() else None

    def _decode(self, raw: bytes) -> np.ndarray:
        if self._codec is not None:
            raw = self._codec.decode(raw)
        return np.frombuffer(raw, dtype=self.dtype).reshape(self.chunks, order=self.order)

    def _load_chunk(self, idx: tuple[int, int, int]) -> np.ndarray | None:
        with self._lock:
            if idx in self._mem:
                self._mem.move_to_end(idx)
                return self._mem[idx]
        name = self.sep.join(str(i) for i in idx)
        raw = None
        cpath = self.cache_dir / name.replace("/", ".") if self.cache_dir else None
        if cpath is not None and cpath.exists():
            raw = cpath.read_bytes()
            if raw == b"":
                raw = None  # cached "missing chunk" marker
            arr = self._decode(raw) if raw is not None else None
        else:
            raw = self._read_bytes(f"{self.array_path}{name}")
            if raw is not None:
                self.fetched_bytes += len(raw)
                self.fetched_chunks += 1
            if cpath is not None:
                tmp = cpath.with_suffix(f".tmp{threading.get_ident()}")
                tmp.write_bytes(raw or b"")
                tmp.replace(cpath)
            arr = self._decode(raw) if raw is not None else None
        with self._lock:
            self._mem[idx] = arr
            while len(self._mem) > self._mem_chunks:
                self._mem.popitem(last=False)
        return arr

    # -- public -----------------------------------------------------------------
    def read(self, lo, hi) -> np.ndarray:
        """Dense sub-volume [lo, hi) in (z, y, x); out-of-bounds is filled with fill_value."""
        lo = np.asarray(lo, dtype=np.int64)
        hi = np.asarray(hi, dtype=np.int64)
        out = np.full(tuple(np.maximum(hi - lo, 0)), self.fill_value, dtype=self.dtype)
        clo = np.maximum(lo, 0)
        chi = np.minimum(hi, self.shape)
        if np.any(chi <= clo):
            return out
        ch = np.asarray(self.chunks)
        c0 = clo // ch
        c1 = (chi - 1) // ch
        idxs = [(i, j, k) for i in range(c0[0], c1[0] + 1) for j in range(c0[1], c1[1] + 1) for k in range(c0[2], c1[2] + 1)]
        if len(idxs) > 1 and self.workers > 1:
            with ThreadPoolExecutor(self.workers) as ex:
                arrs = list(ex.map(self._load_chunk, idxs))
        else:
            arrs = [self._load_chunk(i) for i in idxs]
        for idx, arr in zip(idxs, arrs):
            if arr is None:
                continue
            org = np.asarray(idx) * ch
            s_lo = np.maximum(clo, org)
            s_hi = np.minimum(chi, org + ch)
            src = tuple(slice(a - o, b - o) for a, b, o in zip(s_lo, s_hi, org))
            dst = tuple(slice(a - o, b - o) for a, b, o in zip(s_lo, s_hi, lo))
            out[dst] = arr[src]
        return out

    def sample(self, zyx: np.ndarray, order: int = 1) -> np.ndarray:
        """Interpolate the volume at float (z, y, x) points of shape (..., 3). NaN points give 0."""
        from scipy.ndimage import map_coordinates

        pts = np.asarray(zyx, dtype=np.float32).reshape(-1, 3)
        good = np.isfinite(pts).all(1)
        res = np.zeros(len(pts), dtype=np.float32)
        if good.any():
            g = pts[good]
            # spline prefiltering (order > 1) depends on voxels well beyond the stencil
            halo = 2 if order <= 1 else 10
            lo = np.floor(g.min(0)).astype(np.int64) - halo
            hi = np.ceil(g.max(0)).astype(np.int64) + halo + 1
            if np.prod(hi - lo) <= self.max_block_voxels:
                res[good] = self._sample_block(g, lo, hi, order, map_coordinates)
            else:
                # Points spread over a large region (curved surfaces): sample per block so only the
                # chunks actually touched are held densely, never the whole bounding box.
                keys = np.floor(g / self.block).astype(np.int64)
                _, inv = np.unique(keys, axis=0, return_inverse=True)
                inv = inv.reshape(-1)
                order_idx = np.argsort(inv, kind="stable")
                bounds = np.flatnonzero(np.diff(inv[order_idx])) + 1
                vals = np.empty(len(g), dtype=np.float32)
                for idx in np.split(order_idx, bounds):
                    gb = g[idx]
                    blo = np.floor(gb.min(0)).astype(np.int64) - halo
                    bhi = np.ceil(gb.max(0)).astype(np.int64) + halo + 1
                    vals[idx] = self._sample_block(gb, blo, bhi, order, map_coordinates)
                res[good] = vals
        return res.reshape(np.asarray(zyx).shape[:-1])

    def _sample_block(self, g, lo, hi, order, map_coordinates):
        sub = self.read(lo, hi).astype(np.float32)  # map_coordinates rejects float16
        out = np.empty(len(g), dtype=np.float32)
        map_coordinates(sub, (g - lo).T, output=out, order=order, mode="nearest", prefilter=order > 1)
        return out
