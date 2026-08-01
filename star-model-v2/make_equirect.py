#!/usr/bin/env python3
"""Convert NASA SDO full-disk images into equirectangular sphere textures.

Repo layout (this file lives in star-model-v2/):
  input : ../star-model/assets/nasa/latest_2048_*.jpg   (already in repo)
  output: ./assets/equirect_*.jpg (2048x1024, q90) + equirect_preview.png

Run:  python3 make_equirect.py     (needs: pip install opencv-python numpy pillow)

Pipeline
--------
1. Auto-detect disk (cx, cy, R):
   - largest bright blob for a rough centroid/radius
   - R from the sharp drop of the azimuthally-averaged radial profile
     (robust to bright corona/streamers that break naive thresholding)
   - center refined by maximizing the steepness of that drop
2. Front hemisphere: orthographic inverse mapping, bilinear (cv2.remap).
3. Back hemisphere: heavily blurred mirror of the front, cosine cross-blend
   within +-10 deg of the +-90 deg seam.
"""
import os
import cv2
import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE, "..", "star-model", "assets", "nasa")
OUT_DIR = os.path.join(BASE, "assets")
os.makedirs(OUT_DIR, exist_ok=True)

IMAGES = {
    "0304": "latest_2048_0304.jpg",   # AIA 304 (fuzzy limb)
    "0193": "latest_2048_0193.jpg",   # AIA 193
    "0211": "latest_2048_0211.jpg",   # AIA 211
    "HMIIC": "latest_2048_HMIIC.jpg", # HMI continuum
}

EW, EH = 2048, 1024  # equirect size


# ---------------------------------------------------------------- disk detect
def _largest_blob(g, thresh_frac):
    p95 = np.percentile(g, 95)
    mask = (g > thresh_frac * p95).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    cx, cy = float(cents[idx][0]), float(cents[idx][1])
    R0 = float(np.sqrt(stats[idx, cv2.CC_STAT_AREA] / np.pi))
    return cx, cy, R0


def _annulus_profile(g, cx, cy):
    """Azimuthal mean brightness on a polar grid (240 angles x r=600..1100)."""
    th = np.linspace(0, 2 * np.pi, 240, endpoint=False)
    rs = np.arange(600.0, 1100.0, 4.0)
    TH, RR = np.meshgrid(th, rs)
    xs = np.clip(cx + RR * np.cos(TH), 0, g.shape[1] - 1).astype(np.float32)
    ys = np.clip(cy + RR * np.sin(TH), 0, g.shape[0] - 1).astype(np.float32)
    prof = cv2.remap(g, xs.reshape(1, -1), ys.reshape(1, -1),
                     cv2.INTER_LINEAR).reshape(xs.shape)
    m = np.nanmean(prof, axis=1)
    return rs, cv2.GaussianBlur(m.reshape(-1, 1), (1, 5), 0).ravel()


def _annulus_R(g, cx, cy, lvl):
    """Radius where the azimuthal mean profile drops (persistently) below lvl."""
    rs, m = _annulus_profile(g, cx, cy)
    for i in range(len(rs) - 4):
        if m[i] < lvl and np.all(m[i + 1:i + 5] < lvl * 1.3):
            # interpolate crossing
            if i > 0:
                return float(rs[i - 1] + (lvl - m[i - 1]) /
                             (m[i] - m[i - 1] + 1e-9) * (rs[i] - rs[i - 1]))
            return float(rs[i])
    return 900.0  # fallback


def _drop_steepness(g, cx, cy, R):
    rs, m = _annulus_profile(g, cx, cy)
    sel = (rs >= 0.85 * R) & (rs <= 1.15 * R)
    return float(-np.gradient(m)[sel].min())


def _refine_center(g, cx, cy, R):
    """Hill-climb center to maximize steepness of the radial drop."""
    best = (cx, cy)
    best_s = _drop_steepness(g, cx, cy, R)
    for step in (16, 4, 1):
        improved = False
        for dx in (-step, 0, step):
            for dy in (-step, 0, step):
                if dx == 0 and dy == 0:
                    continue
                s = _drop_steepness(g, best[0] + dx, best[1] + dy, R)
                if s > best_s + 1e-6:
                    best_s, best = s, (best[0] + dx, best[1] + dy)
                    improved = True
        if not improved and step == 4:
            pass
    return best


def detect_disk(gray, thresh_frac=0.25):
    g = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 3)
    h, w = g.shape
    cx, cy, R0 = _largest_blob(g, thresh_frac)
    yy, xx = np.mgrid[0:h, 0:w]
    med = np.median(g[((xx - cx) ** 2 + (yy - cy) ** 2) < 400 ** 2])
    lvl = 0.35 * med
    for _ in range(2):
        R = _annulus_R(g, cx, cy, lvl)
        cx, cy = _refine_center(g, cx, cy, R)
    R = _annulus_R(g, cx, cy, lvl)
    # pull R slightly inside the brightness drop so no dark limb ring is
    # sampled (R is the 0.35*median crossing, i.e. mid-falloff)
    R *= 0.97
    # keep sampling strictly inside the frame (also excludes the watermark)
    R = min(R, min(cx, w - 1 - cx, cy, h - 1 - cy) * 0.995)
    return cx, cy, R


# ------------------------------------------------------ radial flattening
def flatten_radial(img, cx, cy, max_gain=2.8):
    """Remove the large-scale radial brightness falloff (limb drop) so the
    sphere texture has a flat response; the renderer re-applies physical,
    view-dependent limb treatment. Gain is clamped to avoid noise blow-up."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = g.shape
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - cx, yy - cy)
    rmax = int(min(cx, w - cx, cy, h - cy))
    bins = np.arange(0, rmax + 8, 8.0)
    prof = np.zeros(len(bins))
    for i, r in enumerate(bins):
        m = (d >= r) & (d < r + 8)
        prof[i] = g[m].mean() if m.any() else np.nan
    # fill gaps, smooth, normalize to the disk-interior mean
    ok = ~np.isnan(prof)
    prof = np.interp(bins, bins[ok], prof[ok])
    prof = cv2.GaussianBlur(prof.reshape(-1, 1), (1, 15), 0).ravel()
    interior = np.median(prof[: len(prof) // 2])
    gain = np.clip(interior / np.maximum(prof, 1.0), 1.0, max_gain)
    gain_img = np.interp(d, bins, gain).astype(np.float32)
    out = np.clip(img.astype(np.float32) * gain_img[..., None], 0, 255)
    return out.astype(np.uint8)


# -------------------------------------------------------------- equirect map
def make_equirect(img, cx, cy, R):
    """img: HxWx3 uint8 BGR -> 1024x2048x3 uint8 equirect (BGR)."""
    xs = np.arange(EW, dtype=np.float32)
    ys = np.arange(EH, dtype=np.float32)
    lon = (xs / EW) * 2 * np.pi - np.pi            # (EW,)
    lat = np.pi / 2 - (ys / EH) * np.pi            # (EH,)
    LON, LAT = np.meshgrid(lon, lat)

    coslat = np.cos(LAT)
    dy = np.sin(LAT)
    # mirror longitude for the back hemisphere
    lon_f = np.where(LON > np.pi / 2, np.pi - LON,
                     np.where(LON < -np.pi / 2, -np.pi - LON, LON))
    dx_f = coslat * np.sin(lon_f)

    map_x = (cx + R * dx_f).astype(np.float32)
    map_y = (cy - R * dy).astype(np.float32)
    front = cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # back hemisphere: strong blur of the same (mirrored) sampling
    back = cv2.GaussianBlur(front, (0, 0), sigmaX=10, sigmaY=10)

    # cosine cross-blend across +-10 deg around the +-90 deg seam
    seam = np.deg2rad(10.0)
    # s: -1 at seam-10deg ... +1 at seam+10deg (clamped outside)
    s = np.clip((np.abs(LON) - (np.pi / 2 - seam)) / (2 * seam), -1.0, 1.0)
    t = 0.5 - 0.5 * np.cos((s + 1.0) * np.pi / 2.0)   # 0=front ... 1=back

    out = front.astype(np.float32) * (1 - t[..., None]) + \
        back.astype(np.float32) * t[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    previews = []
    for key, fname in IMAGES.items():
        path = os.path.join(SRC_DIR, fname)
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"cannot read {path}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cx, cy, R = detect_disk(gray)
        print(f"{key}: center=({cx:.1f}, {cy:.1f})  R={R:.1f}")
        flat = flatten_radial(img, cx, cy)
        eq = make_equirect(flat, cx, cy, R)
        out_path = os.path.join(OUT_DIR, f"equirect_{key}.jpg")
        rgb = cv2.cvtColor(eq, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(out_path, quality=90)
        print(f"  -> {out_path}")
        previews.append(rgb)

    sheet = np.concatenate(
        [cv2.resize(p, (1024, 512), interpolation=cv2.INTER_AREA)
         for p in previews], axis=1)
    prev = os.path.join(BASE, "equirect_preview.png")
    Image.fromarray(sheet).save(prev)
    print("preview ->", prev)


if __name__ == "__main__":
    main()
