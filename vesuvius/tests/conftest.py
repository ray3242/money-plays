import json

import numpy as np
import pytest

from tifxyz_snap.tifxyz import TifXYZ


def write_zarr(root, vol, chunks=(32, 32, 32), sep="/"):
    """Write a tiny uncompressed Zarr v2 group with one level, without needing zarr installed."""
    lvl = root / "0"
    lvl.mkdir(parents=True)
    (root / ".zgroup").write_text('{"zarr_format": 2}')
    meta = {
        "shape": list(vol.shape),
        "chunks": list(chunks),
        "dtype": "|u1",
        "fill_value": 0,
        "order": "C",
        "filters": None,
        "dimension_separator": sep,
        "compressor": None,
        "zarr_format": 2,
    }
    (lvl / ".zarray").write_text(json.dumps(meta))
    for i in range(0, vol.shape[0], chunks[0]):
        for j in range(0, vol.shape[1], chunks[1]):
            for k in range(0, vol.shape[2], chunks[2]):
                block = np.zeros(chunks, np.uint8)
                part = vol[i : i + chunks[0], j : j + chunks[1], k : k + chunks[2]]
                if not part.any():
                    continue  # leave empty chunks missing, like masked scroll volumes
                block[: part.shape[0], : part.shape[1], : part.shape[2]] = part
                p = lvl / sep.join(str(v // c) for v, c in zip((i, j, k), chunks))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(block.tobytes())
    return root


@pytest.fixture
def sheet_scene(tmp_path):
    """A wavy bright sheet (8 voxels thick) in a 96x160x160 volume, plus a grid surface near its lower face.

    The sheet occupies z in [face - 8, face], so its +z face is at ``face(y, x)``.
    """
    Z, Y, X = 96, 160, 160
    yy, xx = np.mgrid[0:Y, 0:X].astype(np.float32)
    face = 50 + 4 * np.sin(xx / 25.0) + 3 * np.cos(yy / 31.0)
    zz = np.arange(Z, dtype=np.float32)[:, None, None]
    inside = 1 / (1 + np.exp((zz - face[None]) / 0.7)) * 1 / (1 + np.exp((face[None] - 8 - zz) / 0.7))
    rng = np.random.default_rng(0)
    vol = np.clip(40 + 160 * inside + rng.normal(0, 12, (Z, Y, X)), 0, 255).astype(np.uint8)
    root = write_zarr(tmp_path / "vol.zarr", vol)

    step = 4
    gy, gx = np.mgrid[12:148:step, 12:148:step].astype(np.float32)
    true_z = 50 + 4 * np.sin(gx / 25.0) + 3 * np.cos(gy / 31.0)

    def make(dz):
        return TifXYZ(x=gx.copy(), y=gy.copy(), z=(true_z + dz).astype(np.float32), meta={"scale": [1 / step, 1 / step]})

    return root, make, true_z
