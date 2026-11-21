import json

import numpy as np

from tifxyz_snap.cli import main
from tifxyz_snap.mrf import aggregate, argmin_subpixel
from tifxyz_snap.tifxyz import read_tifxyz, write_tifxyz
from tifxyz_snap.volume import ZarrVolume


def test_tifxyz_roundtrip(sheet_scene, tmp_path):
    _, make, _ = sheet_scene
    surf = make(0.0)
    surf.z[0, :3] = -1
    surf.x[0, :3] = -1
    surf.y[0, :3] = -1
    write_tifxyz(tmp_path / "s", surf, extra_meta={"note": "x"})
    back = read_tifxyz(tmp_path / "s")
    np.testing.assert_array_equal(back.z, surf.z)
    assert (back.valid == surf.valid).all()
    assert back.meta["note"] == "x" and back.meta["format"] == "tifxyz"
    assert len(back.meta["bbox"]) == 2


def test_volume_read_matches_numpy_and_handles_missing_chunks(tmp_path):
    from conftest import write_zarr

    rng = np.random.default_rng(1)
    vol = rng.integers(1, 255, (70, 70, 70), dtype=np.uint8)
    vol[:32, :32, :32] = 0  # becomes a missing chunk
    for sep in ("/", "."):
        v = ZarrVolume(str(write_zarr(tmp_path / f"v{sep == '/'}.zarr", vol, sep=sep)))
        np.testing.assert_array_equal(v.read((5, 6, 7), (66, 60, 70)), vol[5:66, 6:60, 7:70])
        out = v.read((-4, 60, 60), (10, 80, 80))  # partly out of bounds
        assert out.shape == (14, 20, 20) and (out[:4] == 0).all()
        np.testing.assert_array_equal(out[4:, :10, :10], vol[:10, 60:70, 60:70])
        pts = np.array([[10.0, 40.0, 40.0], [np.nan, 1, 1]])
        s = v.sample(pts)
        assert s[0] == vol[10, 40, 40] and s[1] == 0


def test_mrf_removes_isolated_outlier():
    d = 21
    cost = np.ones((9, 9, d), np.float32)
    cost[..., 10] = 0.0  # everyone prefers label 10
    cost[4, 4] = 1.0
    cost[4, 4, 18] = 0.0  # one vertex prefers a far label (a neighbouring wrap)
    cost[4, 4, 10] = 0.3
    valid = np.ones((9, 9), bool)
    idx, _conf = argmin_subpixel(aggregate(cost, valid, 0.3, 3.0))
    assert np.allclose(np.round(idx), 10)
    raw, _ = argmin_subpixel(cost)
    assert round(float(raw[4, 4])) == 18


def test_mrf_keeps_real_step_between_disconnected_regions():
    d = 21
    cost = np.ones((6, 12, d), np.float32)
    cost[:, :5, 4] = 0
    cost[:, 7:, 16] = 0
    valid = np.ones((6, 12), bool)
    valid[:, 5:7] = False  # a hole separates the two regions
    idx, _ = argmin_subpixel(aggregate(cost, valid, 0.3, 3.0))
    assert np.allclose(np.round(idx[:, :5]), 4) and np.allclose(np.round(idx[:, 7:]), 16)


def test_cli_end_to_end(sheet_scene, tmp_path, capsys):
    root, make, true_z = sheet_scene
    write_tifxyz(tmp_path / "in", make(3.0))
    out = tmp_path / "out"
    rc = main(["snap", str(tmp_path / "in"), str(root), "-o", str(out), "--search", "6", "--patch", "1", "--patch-spacing", "1.5", "--sigma", "1"])
    assert rc == 0
    snapped = read_tifxyz(out)
    assert np.abs(snapped.z - true_z)[2:-2, 2:-2].mean() < 0.6
    report = json.loads((out / "snap_report.json").read_text())
    assert report["after"]["edge_strength_mean"] > report["before"]["edge_strength_mean"]
    assert snapped.meta["tifxyz_snap"]["target"] == "edge-"
    for f in ("snap_offset.tif", "snap_confidence.tif", "qa/sections.png", "qa/offset_map.png"):
        assert (out / f).exists()
    assert main(["render", str(out), str(root), "-o", str(tmp_path / "tex.png"), "--window", "2", "20", "2", "20"]) == 0
    assert (tmp_path / "tex.png").exists()


def test_volume_sample_blockwise_matches_dense(tmp_path):
    from conftest import write_zarr

    rng = np.random.default_rng(2)
    vol = rng.integers(0, 255, (70, 70, 70), dtype=np.uint8)
    v = ZarrVolume(str(write_zarr(tmp_path / "b.zarr", vol, sep="/")))
    pts = rng.uniform(1, 68, (500, 3))
    dense = v.sample(pts)
    v.block, v.max_block_voxels = 16, 1
    np.testing.assert_allclose(v.sample(pts), dense, atol=1e-4)


def test_z_zero_is_a_valid_vertex():
    from tifxyz_snap.tifxyz import TifXYZ

    s = TifXYZ(x=np.ones((2, 2), np.float32), y=np.ones((2, 2), np.float32), z=np.zeros((2, 2), np.float32), meta={})
    assert s.valid.all()


def test_standalone_zarr_array_and_unsafe_codec(tmp_path):
    import pytest
    from conftest import write_zarr

    vol = np.arange(40**3, dtype=np.uint32).reshape(40, 40, 40).astype(np.uint8)
    root = write_zarr(tmp_path / "s.zarr", vol)
    flat = tmp_path / "flat.zarr"
    (root / "0").rename(flat)
    np.testing.assert_array_equal(ZarrVolume(str(flat)).read((0, 0, 0), (40, 40, 40)), vol)
    meta = json.loads((flat / ".zarray").read_text())
    meta["compressor"] = {"id": "pickle"}
    (flat / ".zarray").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="unsupported"):
        ZarrVolume(str(flat))


def test_cli_on_empty_volume_writes_report(sheet_scene, tmp_path, capsys):
    from conftest import write_zarr

    _, make, _ = sheet_scene
    root = write_zarr(tmp_path / "empty.zarr", np.zeros((96, 160, 160), np.uint8))
    write_tifxyz(tmp_path / "in", make(0.0))
    out = tmp_path / "out"
    assert main(["snap", str(tmp_path / "in"), str(root), "-o", str(out), "--search", "6", "--patch", "1", "--sigma", "1"]) == 0
    assert json.loads((out / "snap_report.json").read_text())["vertices"] == 0
    assert main(["validate", str(tmp_path / "in"), str(root), "--search", "6", "--patch", "1", "--sigma", "1"]) == 0
