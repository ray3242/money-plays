"""Do snaps computed from independent CT scans of the same scroll agree?

The same PHerc. 814 segment is published registered onto three different scans
(different dates, beam energies and resolutions). Snapping it against each scan
independently gives three offset fields for the same grid vertices. If the snapper
followed noise they would be unrelated; if it follows the papyrus they agree.
"""

import itertools
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import tifffile

out = Path(sys.argv[1])
UM = {"scan_9.362um": 9.362, "scan_2.399um": 2.399 * 4, "scan_1.129um": 1.129 * 8}  # voxel size of the level used
off = {k: tifffile.imread(out / k / "snap_offset.tif") * um for k, um in UM.items() if (out / k).exists()}
res = {}
pairs = list(itertools.combinations(off, 2))
fig, axes = plt.subplots(1, len(pairs), figsize=(6 * len(pairs), 5.5), squeeze=False)
for ax, (a, b) in zip(axes[0], pairs):
    m = (off[a] != 0) & (off[b] != 0)
    x, y = off[a][m], off[b][m]
    d = x - y
    res[f"{a} vs {b}"] = {
        "vertices": int(m.sum()),
        "pearson_r": round(float(np.corrcoef(x, y)[0, 1]), 3),
        "median_abs_diff_um": round(float(np.median(np.abs(d))), 2),
        "within_10um": round(float((np.abs(d) < 10).mean()), 3),
        "offset_rms_um": [round(float(np.sqrt((x**2).mean())), 1), round(float(np.sqrt((y**2).mean())), 1)],
    }
    ax.hexbin(x, y, gridsize=80, extent=(-80, 80, -80, 80), bins="log", cmap="magma")
    ax.plot([-80, 80], [-80, 80], color="c", lw=0.8)
    ax.set_xlabel(f"snap offset from {a} (um)")
    ax.set_ylabel(f"snap offset from {b} (um)")
    ax.set_title(f"r = {res[f'{a} vs {b}']['pearson_r']}, {100 * res[f'{a} vs {b}']['within_10um']:.0f}% within 10 um")
    ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(out / "cross_scan_agreement.png", dpi=90)
(out / "cross_scan_agreement.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
