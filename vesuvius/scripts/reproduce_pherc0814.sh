#!/usr/bin/env bash
# Reproduce every number and figure in the README on public PHerc. 814 data.
# Needs ~20 GB of free disk for the chunk cache, no GPU, no credentials.
set -euo pipefail

B=https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0814
SEG=$B/segments/20250929040153-auto_grown_20250929040153260/mesh
WORK=${1:-./pherc0814_demo}
CACHE=${TIFXYZ_SNAP_CACHE:-$HOME/.cache/tifxyz-snap}
mkdir -p "$WORK/in" "$WORK/out"

# name | mesh on that scan | volume | pyramid level (all three end up at ~9-10 um voxels)
RUNS=(
  "scan_9.362um|20250929040153-on-20250804134230-9.362um|20250804134230-9.362um-1.2m-113keV-masked.zarr|0"
  "scan_2.399um|20250929040153-on-20260309142202-2.399um-t2|20260309142202-2.399um-0.2m-78keV-masked.zarr|2"
  "scan_1.129um|20250929040153-on-20260521123630-1.129um-t2|20260521123630-1.129um-0.2m-59keV-masked.zarr|3"
)

for run in "${RUNS[@]}"; do
  IFS='|' read -r name mesh vol level <<<"$run"
  for f in x.tif y.tif z.tif meta.json; do
    [ -f "$WORK/in/$name/$f" ] || curl -sf --create-dirs -o "$WORK/in/$name/$f" "$SEG/$mesh.tifxyz/$f"
  done
  tifxyz-snap snap "$WORK/in/$name" "$B/volumes/$vol" --level "$level" --cache "$CACHE" -o "$WORK/out/$name"
  tifxyz-snap validate "$WORK/in/$name" "$B/volumes/$vol" --level "$level" --cache "$CACHE" -o "$WORK/out/$name/validate.json"
done

python "$(dirname "$0")/cross_scan_agreement.py" "$WORK/out"
