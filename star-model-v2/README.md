# Star Model v2 — NASA-realistic SDO Sun

Upgraded 3D star render: real NASA SDO data, properly equirect-mapped onto the sphere.

## What's new vs `star-model/`

| area | v1 | v2 |
|---|---|---|
| texture mapping | square photo wrapped with UV repeat (artifacts) | true equirectangular projection (orthographic → equirect conversion) |
| resolution | 1024 px | 2048 px source SDO frames |
| wavelengths | 1 (AIA 304) | 4 with in-shader crossfade: 304 Å, 193 Å, 211 Å, HMI continuum |
| limb physics | none | physical limb darkening (HMI, u=0.64) / EUV limb brightening |
| corona | single uniform shell | two-layer: fresnel inner glow + equatorial streamer field (1/r^2.2, fBm streaks, solar-minimum morphology) |
| prominences | random on-disk sprites | sprites + torus arcs pinned to the camera limb silhouette |
| tone mapping | Reinhard | ACES filmic + tuned UnrealBloom |

## Files

- `index.html` — the model (self-contained; Three.js 0.160 via unpkg importmap)
- `make_equirect.py` — regenerates `assets/equirect_*.jpg` from the SDO frames already in this repo (`../star-model/assets/nasa/`)

## Regenerating textures

```bash
pip install opencv-python numpy pillow
cd star-model-v2
python3 make_equirect.py
# → assets/equirect_{0304,0193,0211,HMIIC}.jpg + equirect_preview.png
```

The equirect JPGs are derived assets (regenerable), so they are not committed;
`index.html` shows a procedural warm-plasma fallback if they are missing.

## Pipeline (make_equirect.py)

1. Auto-detect disk `(cx, cy, R)` per frame — azimuthal radial profile drop, robust to bright corona; center refined by drop-steepness hill-climb; watermark auto-excluded.
2. Radial flattening (gain ≤ 2.8×) — the renderer re-applies physical limb response, so the texture must be flat.
3. Front hemisphere: inverse orthographic sampling (bilinear). Back hemisphere: blurred mirror, cosine cross-blend ±10° around the ±90° seam.

Data: NASA SDO/AIA + HMI (frames of 2026-05-05, 2048 px).
