import numpy as np

from tifxyz_snap.snap import SnapConfig, snap
from tifxyz_snap.validate import perturbation_recovery
from tifxyz_snap.volume import ZarrVolume

CFG = {"search": 6, "patch": 1, "patch_spacing": 1.5, "sigma": 1.0}


def test_snaps_biased_surface_back_to_sheet_face(sheet_scene):
    root, make, true_z = sheet_scene
    vol = ZarrVolume(str(root))
    surf = make(3.0)  # 3 voxels off the face, in the air
    res = snap(surf, vol, SnapConfig(target="edge-", **CFG))
    before = np.abs(surf.z - true_z)[2:-2, 2:-2]
    after = np.abs(res.surface.z - true_z)[2:-2, 2:-2]
    assert before.mean() > 2.9
    assert after.mean() < 0.6
    assert (after < 1.0).mean() > 0.95


def test_auto_edge_sign_and_noop_when_already_on_face(sheet_scene):
    root, make, true_z = sheet_scene
    vol = ZarrVolume(str(root))
    res = snap(make(0.5), vol, SnapConfig(target="edge", **CFG))
    assert res.config["target"] == "edge-"  # grid normal points to -z, air is on +z
    assert np.abs(res.surface.z - true_z)[2:-2, 2:-2].mean() < 0.6


def test_center_target_goes_to_sheet_midline(sheet_scene):
    root, make, true_z = sheet_scene
    vol = ZarrVolume(str(root))
    res = snap(make(-1.0), vol, SnapConfig(target="center", sigma=2.0, search=6, patch=1, patch_spacing=1.5))
    mid = true_z - 4
    assert np.abs(res.surface.z - mid)[2:-2, 2:-2].mean() < 0.8


def test_invalid_vertices_are_preserved(sheet_scene):
    root, make, _ = sheet_scene
    vol = ZarrVolume(str(root))
    surf = make(2.0)
    for g in (surf.x, surf.y, surf.z):
        g[5:9, 5:9] = -1
    res = snap(surf, vol, SnapConfig(target="edge-", **CFG))
    assert (res.surface.z[5:9, 5:9] == -1).all()
    assert (res.surface.valid == surf.valid).all()
    assert np.isnan(res.offset[5:9, 5:9]).all()


def test_surface_in_empty_space_does_not_move(sheet_scene, tmp_path):
    from conftest import write_zarr

    root = write_zarr(tmp_path / "empty.zarr", np.zeros((96, 160, 160), np.uint8))
    _, make, _ = sheet_scene
    surf = make(0.0)
    res = snap(surf, ZarrVolume(str(root)), SnapConfig(**CFG))
    np.testing.assert_allclose(res.surface.z, surf.z)


def test_perturbation_recovery(sheet_scene):
    root, make, _ = sheet_scene
    vol = ZarrVolume(str(root))
    m, _, _ = perturbation_recovery(make(1.0), vol, SnapConfig(target="edge-", **CFG), rms=1.5, corr=4)
    assert m["residual_rms_vox"] < 0.4 * m["perturbation_rms_vox"]
    assert m["within_1_vox"] > 0.95


def test_uniform_bright_region_does_not_move(sheet_scene, tmp_path):
    from conftest import write_zarr

    root = write_zarr(tmp_path / "flat.zarr", np.full((96, 160, 160), 100, np.uint8))
    _, make, _ = sheet_scene
    surf = make(0.0)
    res = snap(surf, ZarrVolume(str(root)), SnapConfig(**CFG))
    np.testing.assert_allclose(res.surface.z, surf.z, atol=1e-4)


def test_small_search_keeps_zero_candidate(sheet_scene):
    root, make, _ = sheet_scene
    surf = make(0.0)
    res = snap(surf, ZarrVolume(str(root)), SnapConfig(search=0.2, step=1.0, sigma=1.05, patch=1, patch_spacing=1.5))
    assert np.nanmax(np.abs(res.offset)) <= 0.2 + 1e-6
