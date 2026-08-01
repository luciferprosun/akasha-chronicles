# Star Model v3 — NASA-realistic SDO Sun (true 360° synoptic)

3D star render on **real NASA SDO data covering the whole sphere**: synoptic
Carrington-style mosaic from 31 days of SDO browse frames (2026-04-19 →
2026-05-19, anchored 2026-05-05), all four channels (AIA 304/193/211 Å + HMI
continuum).

## Why synoptic?

SDO only photographs the Earth-facing hemisphere. v2 mirrored+blurred the far
side. v3 builds the full 360° the same way NASA builds synoptic maps: the Sun
rotates ~13.19°/day (synodic), so the central-meridian strips of ~28+ days
cover all longitudes. Consequence: the far side is real data, time-shifted by
up to ±15 days (active regions evolve) — that is inherent to every synoptic
map, not a bug.

## What's new vs `star-model/` (v1)

| area | v1 | v3 |
|---|---|---|
| texture mapping | square photo wrapped with UV repeat (artifacts) | true equirect + full 360° synoptic mosaic |
| far hemisphere | (absent) | real SDO data (time-shifted) |
| resolution | 1024 px | 2048 px maps from 1024–2048 px SDO frames |
| wavelengths | 1 (AIA 304) | 4 with in-shader crossfade: 304 Å, 193 Å, 211 Å, HMI continuum |
| limb physics | none | physical limb darkening (HMI, u=0.64) / EUV limb brightening |
| corona | single uniform shell | two-layer: fresnel inner glow + equatorial streamer field (1/r^2.2, fBm streaks, solar-minimum morphology) |
| prominences | random on-disk sprites | sprites + torus arcs pinned to the camera limb silhouette |
| tone mapping | Reinhard | ACES filmic + tuned UnrealBloom |

## Files

- `index.html` — the model (self-contained; Three.js 0.160 via unpkg importmap).
  URL param `?lon=180` starts on the far side.
- `fetch_sdo.py` — downloads the 31-day frame set from the SDO browse archive
  (`synoptic_raw/`, resilient: truncated listings, parallel curl, JPEG verify).
- `make_synoptic.py` — builds `assets/equirect_syn_*.jpg` (2048×1024) from the
  raw frames; `--check-sign` verifies the rotation sign convention by
  adjacent-day strip correlation.
- `make_equirect.py` — single-frame equirect converter (v2 pipeline; shared
  disk-detection / radial-flattening functions).

## Rebuild from scratch

```bash
pip install opencv-python numpy pillow
cd star-model-v2
python3 fetch_sdo.py                 # 124 files, ~30 MB
python3 make_synoptic.py --check-sign
# → assets/equirect_syn_{0304,0193,0211,HMIIC}.jpg + synoptic_preview.png
python3 -m http.server               # serve over http (Chrome blocks file:// textures)
```

The equirect JPGs are derived assets (regenerable), so they are not committed;
`index.html` shows a procedural warm-plasma fallback if they are missing.

## Mosaic pipeline (make_synoptic.py)

1. Per daily frame: disk detect (azimuthal radial-profile drop, robust to
   bright corona) + radial flattening (gain ≤ 2.8×) + disk-mean brightness.
2. Day n's central-meridian map longitude: λ_cm = −13.19°·n (sign verified
   empirically, overlap-strip Pearson 0.55 vs 0.02 for the flipped sign).
3. Every equirect pixel gets raised-cosine-weighted contributions from the
   1–4 days whose strips cover it; per-day brightness normalized first
   (kills exposure banding).
4. Weight taper near the limb (EUV dark moat / polar coronal holes);
   zero-weight polar caps inpainted (TELEA) — polar detail is physically
   unobservable from the ecliptic in EUV.

Data: NASA SDO/AIA + HMI browse archive (sdo.gsfc.nasa.gov), frames of
2026-04-19 → 2026-05-19.
