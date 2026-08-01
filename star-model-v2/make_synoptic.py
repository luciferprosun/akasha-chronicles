#!/usr/bin/env python3
"""Build TRUE 360-degree synoptic equirect textures from ~31 days of SDO
browse images (Carrington-style mosaic).

Per channel:
  1. detect disk (reusing make_equirect.detect_disk, on a 2x-upscaled frame
     because its annulus range is tuned for 2048px), flatten radial falloff
     FIRST (reusing make_equirect.flatten_radial), record disk mean.
  2. day offset n = date - 2026-05-05; central-meridian map longitude
     lam_cm(n) = sign * (-13.19 deg/day) * n   (synodic rate)
  3. for every equirect pixel (lam, phi), each day with
     |lam_rel| <= 12 deg (lam_rel = wrap(lam - lam_cm)) contributes
     I(cx + R cos(phi) sin(lam_rel), cy - R sin(phi)) with raised-cosine
     weight w = cos(pi * lam_rel / 24 deg).
  4. each day's strip is brightness-normalized (disk mean -> global target)
     BEFORE accumulation to kill exposure banding.
  5. pixels with ~no weight are inpainted (no black bands).

Outputs 2048x1024 JPG q90 per channel into ./assets/ + a contact-sheet
preview with a coverage/diagnostic panel.

Sign convention: verified by --check-sign (adjacent-day overlap correlation);
the physically-correct sign yields consistent features across day strips.
"""
import os, sys, json, datetime
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_equirect import detect_disk, flatten_radial

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "synoptic_raw")
OUT_DIR = os.path.join(BASE, "assets")
ANCHOR = datetime.date(2026, 5, 5)
RATE = 13.19          # deg/day synodic
HALF_DEG = 12.0       # strip half-width
EW, EH = 2048, 1024
CHANNELS = ["0304", "HMIIC", "0193", "0211"]

# Weight taper vs sample radius fraction: full weight up to T0*R, zero at
# T1*R.  EUV 193/211 have a dark moat + polar coronal holes reaching far
# inside the detected limb, so their taper starts deeper (the resulting
# polar caps are inpainted from the bright ring at the cap boundary).
TAPER = {"0193": (0.85, 0.90), "0211": (0.85, 0.90)}


def list_days(channel):
    d = os.path.join(RAW, channel)
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".jpg"):
            try:
                date = datetime.date.fromisoformat(f[:-4])
            except ValueError:
                continue
            out.append((date, os.path.join(d, f)))
    return out


def load_day(path):
    """-> (flat float32 img, cx, cy, R, disk_mean) at native 1024px."""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    up = cv2.resize(img, (2048, 2048), interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    cx, cy, R = detect_disk(gray)
    cx, cy, R = cx / 2.0, cy / 2.0, R / 2.0
    flat = flatten_radial(img, cx, cy).astype(np.float32)
    h, w = flat.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < (0.9 * R) ** 2
    mean = float(flat[mask].mean())
    return flat, cx, cy, R, mean


def wrap_pi(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def build(channel, sign=1.0, ew=EW, eh=EH, verbose=True):
    """-> (map BGR uint8, coverage-count map, list of (date,n,mean,cx,cy,R))"""
    days = list_days(channel)
    if not days:
        raise RuntimeError(f"no raw images for {channel}")
    xs = np.arange(ew, dtype=np.float64)
    ys = np.arange(eh, dtype=np.float64)
    lon = (xs / ew) * 2 * np.pi - np.pi
    lat = np.pi / 2 - (ys / eh) * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    coslat = np.cos(LAT)
    sinlat = np.sin(LAT)
    half = np.deg2rad(HALF_DEG)

    loaded = []
    for date, path in days:
        try:
            flat, cx, cy, R, mean = load_day(path)
        except Exception as e:
            print(f"  !! {channel} {date}: {e} -- skipped", flush=True)
            continue
        n = (date - ANCHOR).days
        loaded.append((date, n, flat, cx, cy, R, mean))
    if not loaded:
        raise RuntimeError(f"no usable images for {channel}")
    target = float(np.median([m for *_, m in loaded]))
    if verbose:
        print(f"{channel}: {len(loaded)} days, target mean {target:.1f}", flush=True)

    acc = np.zeros((eh, ew, 3), np.float64)
    wacc = np.zeros((eh, ew), np.float64)
    cnt = np.zeros((eh, ew), np.int32)
    info = []
    for date, n, flat, cx, cy, R, mean in loaded:
        scale = target / max(mean, 1e-6)
        lam_cm = np.deg2rad(sign * (-RATE) * n)
        rel = wrap_pi(LON - lam_cm)
        sel = np.abs(rel) <= half
        dx = coslat * np.sin(rel)
        # taper weight to zero as the sample radius approaches the limb
        # (EUV dark moat / falloff); polar caps then get no weight and are
        # filled by the inpaint pass below instead of sampling black limb px
        r_frac = np.sqrt(dx * dx + sinlat * sinlat)
        t0, t1 = TAPER.get(channel, (0.92, 0.96))
        taper = np.clip((t1 - r_frac) / (t1 - t0), 0.0, 1.0)
        w = np.where(sel, np.cos(np.pi * rel / (2 * half)), 0.0) * taper
        map_x = (cx + R * dx).astype(np.float32)
        map_y = (cy - R * sinlat).astype(np.float32)
        strip = cv2.remap(flat * scale, map_x, map_y,
                          interpolation=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        acc += strip * w[..., None]
        wacc += w
        cnt += (w > 0.05).astype(np.int32)
        info.append((date, n, mean, cx, cy, R))
        if verbose:
            print(f"  {channel} {date} n={n:+d} lam_cm={np.rad2deg(lam_cm):+7.2f} "
                  f"mean={mean:.1f} scale={scale:.3f}", flush=True)

    eps = 0.02
    out = acc / np.maximum(wacc, eps)[..., None]
    out = np.clip(out, 0, 255).astype(np.uint8)
    missing = (wacc < eps).astype(np.uint8) * 255
    nmissing = int((missing > 0).sum())
    if nmissing:
        if verbose:
            print(f"  {channel}: inpainting {nmissing} px "
                  f"({100*nmissing/(ew*eh):.2f}%)", flush=True)
        out = cv2.inpaint(out, missing, 5, cv2.INPAINT_TELEA)
    return out, cnt, info


def overlap_score(channel, sign, n_pairs=8):
    """Mean Pearson correlation between adjacent days' normalized strips in
    their overlap region. Higher => correct sign."""
    days = list_days(channel)
    data = {}
    for date, path in days:
        try:
            flat, cx, cy, R, mean = load_day(path)
        except Exception:
            continue
        n = (date - ANCHOR).days
        data[n] = (cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY) / max(mean, 1e-6),
                   cx, cy, R)
    ns = sorted(data)
    lons = np.deg2rad(np.arange(-12.0, 12.01, 2.0))
    lats = np.deg2rad(np.arange(-60.0, 60.01, 6.0))
    corrs = []
    pairs = 0
    for a, b in zip(ns[:-1], ns[1:]):
        if b - a != 1 or pairs >= n_pairs:
            continue
        # overlap longitudes: |lam - lam_cm(a)| <= 12 and |lam - lam_cm(b)| <= 12
        la_cm = np.deg2rad(sign * (-RATE) * a)
        lb_cm = np.deg2rad(sign * (-RATE) * b)
        va, vb = [], []
        for lat in lats:
            for lam in np.deg2rad(np.arange(-180, 180, 3.0)):
                ra = wrap_pi(lam - la_cm)
                rb = wrap_pi(lam - lb_cm)
                if abs(ra) <= np.deg2rad(11) and abs(rb) <= np.deg2rad(11):
                    for (img, cx, cy, R), r in ((data[a], ra), (data[b], rb)):
                        x = cx + R * np.cos(lat) * np.sin(r)
                        y = cy - R * np.sin(lat)
                        mx = np.array([[x]], np.float32)
                        my = np.array([[y]], np.float32)
                        v = cv2.remap(img, mx, my, cv2.INTER_LINEAR)[0, 0]
                        (va if r is ra else vb).append(v)
        if len(va) > 50:
            va, vb = np.array(va), np.array(vb)
            if va.std() > 1e-6 and vb.std() > 1e-6:
                corrs.append(float(np.corrcoef(va, vb)[0, 1]))
                pairs += 1
    return float(np.mean(corrs)) if corrs else 0.0, len(corrs)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    do_check = "--check-sign" in sys.argv
    chans = [a for a in sys.argv[1:] if not a.startswith("--")] or CHANNELS

    sign = 1.0
    if do_check:
        s_plus, np1 = overlap_score("0304", +1.0)
        s_minus, np2 = overlap_score("0304", -1.0)
        print(f"SIGN CHECK 0304: corr(sign=+1)={s_plus:.4f} ({np1} pairs)  "
              f"corr(sign=-1)={s_minus:.4f} ({np2} pairs)", flush=True)
        sign = 1.0 if s_plus >= s_minus else -1.0
        print(f"using sign={sign:+.0f}", flush=True)

    previews, covs = [], []
    for ch in chans:
        out, cnt, info = build(ch, sign=sign)
        rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
        path = os.path.join(OUT_DIR, f"equirect_syn_{ch}.jpg")
        Image.fromarray(rgb).save(path, quality=90)
        print(f"  -> {path}  (coverage min/max days per px: "
              f"{cnt.min()}/{cnt.max()})", flush=True)
        previews.append((ch, out))
        covs.append((ch, cnt))

    # ---- contact sheet: maps + coverage/diagnostic panel (all BGR)
    rows = []
    for ch, bgr in previews:
        rows.append(cv2.resize(bgr, (1408, 704), interpolation=cv2.INTER_AREA))
    # diagnostic panel: coverage count as grayscale + text
    panel_rows = []
    for ch, cnt in covs:
        c = np.clip(cnt.astype(np.float32) / 3.0 * 255, 0, 255).astype(np.uint8)
        c = cv2.applyColorMap(c, cv2.COLORMAP_VIRIDIS)
        c = cv2.resize(c, (640, 320), interpolation=cv2.INTER_NEAREST)
        cv2.putText(c, f"{ch} day-count/px min={cnt.min()} max={cnt.max()}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        panel_rows.append(c)
    H = sum(r.shape[0] for r in rows)
    pw = panel_rows[0].shape[1] if panel_rows else 0
    sheet = np.zeros((H, 1408 + pw, 3), np.uint8)
    y = 0
    for i, r in enumerate(rows):
        sheet[y:y + r.shape[0], :1408] = r
        # stack 2 panel rows per map row
        for j in range(2):
            idx = i * 2 + j
            if idx < len(panel_rows):
                pr = panel_rows[idx]
                ph = r.shape[0] // 2
                sheet[y + j * ph:y + (j + 1) * ph, 1408:] = cv2.resize(
                    pr, (pw, ph), interpolation=cv2.INTER_NEAREST)
        y += r.shape[0]
    prev = os.path.join(BASE, "synoptic_preview.png")
    cv2.imwrite(prev, sheet)
    print("preview ->", prev, flush=True)


if __name__ == "__main__":
    main()
