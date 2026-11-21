# Progress prize submission draft

Form: https://docs.google.com/forms/d/e/1FAIpQLSeB6MC_--4UCCEGc3zalX57-uE4puRcE_vJoYJCrEt4uYaaaw/viewform
(linked from https://scrollprize.org/prizes, "Progress Prizes". Next deadline: November 30, 2026, 11:59pm Pacific.)

The form has five questions plus a terms checkbox. Answers below are ready to paste; the submitter fills in the name and Discord fields.

## Your full name

(submitter's legal name)

## Team description

Individual. The code was written with heavy use of an AI coding agent (Devin), directed, run and checked by me on real scroll data.

## Discord display name (optional)

(leave blank or fill in)

## URL of your contribution

https://github.com/ray3242/money-plays/tree/main/vesuvius

Install: `pip install "git+https://github.com/ray3242/money-plays#subdirectory=vesuvius"`

## What is your contribution?

tifxyz-snap is a CPU-only label-snapping tool for the "label snapping" direction in the 2026 open problems. It takes an approximate tifxyz surface and a Zarr / OME-Zarr volume (local or the public S3 bucket, streaming only the chunks it needs) and moves every vertex along its normal onto the papyrus sheet face in the raw CT. The method is a normal-ray edge cost, 8-direction semi-global matching with a truncated-linear smoothness term (so the surface moves coherently but may still step across real discontinuities and holes), sub-step refinement and two passes. No model, no training data, no GPU; a 40k-vertex segment takes about 16 s on 8 cores once its chunks are cached. Output is a new tifxyz on the same grid plus an offset map, a confidence map, a JSON report and QA figures.

(1) Scroll data: PHerc. 814, segment 20250929040153 (auto_grown_20250929040153260, 40.6k vertices), as published registered onto three independent scans: 9.362 um (20250804134230), 2.399 um (20260309142202) and 1.129 um (20260521123630).

(2) Why it helps reading: auto-grown and hand-made surfaces are often a voxel or two off the sheet, which blurs the rendered layers that ink detection and annotators look at, and correcting that by hand is slow. tifxyz-snap does it automatically in seconds on a laptop, in the community's own formats (tifxyz in, tifxyz out, OME-Zarr volumes), so it can sit between segmentation and rendering in any pipeline, including on surfaces produced by VC3D.

(3) What it enables: a cheap, model-free clean-up pass for any existing tifxyz surface on any scan, with a per-vertex confidence map that flags where the sheet is ambiguous. It needs no labelled data, so it works on new scrolls and new scans on day one.

(4) Evidence, all reproducible from public data with one script (scripts/reproduce_pherc0814.sh, no credentials):
- Cross-scan agreement: snapping the same grid against three independent scans (different dates, beam energies and resolutions) gives the same correction, Pearson r 0.87-0.93, median disagreement 2.9-5.0 um, 90-96% of vertices within 10 um, against corrections of about 18-20 um RMS. A snapper that followed noise would give uncorrelated fields.
- Perturbation recovery on the real segment: a smooth 1.45-voxel RMS perturbation along the normal comes back to the first answer with 0.21-voxel median residual, 91% within 1 voxel.
- Cross sections (input in red, snapped in cyan) and before/after flattened textures with fibres visible and no sheet jumps are in the README.
- Limitations stated plainly: no hand-checked ground truth yet, no ink-detection measurement yet, one segment of one scroll, and a 4-9% tail that can lock onto a neighbouring edge under large perturbations.

MIT licensed. 12 regression tests on a synthetic sheet with known ground truth; usefulness claims rest on the real-scroll runs.

## In your own words (please write this part yourself)

The Vesuvius Challenge's contributing guidelines ask that LLM-built work comes with human-written commentary on why it is useful. Add two or three sentences of your own to the end of the answer above, for example what you looked at in the figures and why you think it helps.
