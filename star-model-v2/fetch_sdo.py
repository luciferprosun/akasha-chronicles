#!/usr/bin/env python3
"""Fetch 31 days of SDO browse images (1024px) for the synoptic mosaic.

Network-hardened:
- day listings are fetched TRUNCATED (first chunk of transfer): they are
  chronological, so all near-00:00 UT frames appear in the head.
- downloads run 6-way parallel with retries + PIL completeness checks.

Usage: python3 fetch_sdo.py
  -> synoptic_raw/{channel}/{date}.jpg + synoptic_raw/selection.json
"""
import os, re, sys, json, subprocess, datetime, concurrent.futures, time, threading

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "synoptic_raw")
SEL_JSON = os.path.join(RAW, "selection.json")
ROOT = "https://sdo.gsfc.nasa.gov/assets/img/browse"

D0 = datetime.date(2026, 4, 19)
D1 = datetime.date(2026, 5, 19)
DATES = [(D0 + datetime.timedelta(days=i)) for i in range((D1 - D0).days + 1)]
ALL_CHANNELS = ["0304", "HMIIC", "0193", "0211"]
FNAME_RE = re.compile(r'href="(\d{8}_\d{6}_1024_([A-Za-z0-9]+)\.jpg)"')


def curl_get(url, max_time):
    try:
        r = subprocess.run(["curl", "-sf", "--max-time", str(max_time), url],
                           capture_output=True, timeout=max_time + 30)
        return r.stdout if r.stdout else None
    except Exception:
        return None


def get_listing_head(d):
    """First chunk of the day listing (chronological => covers 00:00-~05:00)."""
    url = f"{ROOT}/{d:%Y/%m/%d}/"
    for mt in (50, 80, 120):
        data = curl_get(url, mt)
        if data:
            return data.decode("utf8", "replace")
    return ""


def build_selection():
    sel = {c: {} for c in ALL_CHANNELS}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        heads = dict(zip(DATES, ex.map(get_listing_head, DATES)))
    for d in DATES:
        text = heads[d]
        latest_t = -1
        best = {c: None for c in ALL_CHANNELS}
        for m in FNAME_RE.finditer(text):
            fname, ch = m.group(1), m.group(2)
            if fname[:8] != d.strftime("%Y%m%d"):
                continue
            hh, mm, ss = int(fname[9:11]), int(fname[11:13]), int(fname[13:15])
            t = hh * 3600 + mm * 60 + ss
            latest_t = max(latest_t, t)
            if ch not in ALL_CHANNELS:
                continue
            dist = min(t, 86400 - t)
            if best[ch] is None or dist < best[ch][1]:
                best[ch] = (fname, dist, t)
        for c in ALL_CHANNELS:
            if best[c] is not None:
                sel[c][d.isoformat()] = [best[c][0], best[c][2]]
        print(f"{d}: head covers to {latest_t//3600:02d}:{(latest_t%3600)//60:02d}  "
              + " ".join(f"{c}={'%02d:%02d'%(sel[c][d.isoformat()][1]//3600,(sel[c][d.isoformat()][1]%3600)//60) if d.isoformat() in sel[c] else '--'}" for c in ALL_CHANNELS),
              flush=True)
    os.makedirs(RAW, exist_ok=True)
    with open(SEL_JSON, "w") as f:
        json.dump(sel, f, indent=1)
    return sel


def verify_jpeg(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            return im.size[0] >= 500 and im.size[1] >= 500
    except Exception:
        return False


def download_one(job):
    ch, date_iso, fname = job
    dest = os.path.join(RAW, ch, date_iso + ".jpg")
    if os.path.exists(dest) and verify_jpeg(dest):
        return (job, "cached")
    url = f"{ROOT}/{date_iso[:4]}/{date_iso[5:7]}/{date_iso[8:10]}/{fname}"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + f".tmp{os.getpid()}_{threading.get_ident()}"
    for attempt in range(4):
        data = curl_get(url, 120)
        if data:
            try:
                with open(tmp, "wb") as f:
                    f.write(data)
                if verify_jpeg(tmp):
                    os.replace(tmp, dest)
                    return (job, "ok")
            except OSError:
                pass
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        time.sleep(1 + attempt)
    try:
        os.remove(dest)
    except OSError:
        pass
    return (job, "FAIL")


def main():
    if os.path.exists(SEL_JSON):
        with open(SEL_JSON) as f:
            sel = json.load(f)
        print("loaded existing selection.json")
    else:
        sel = build_selection()
    # mandatory first, then optional
    jobs, gaps = [], []
    for c in ALL_CHANNELS:
        for d in DATES:
            iso = d.isoformat()
            if iso in sel.get(c, {}):
                jobs.append((c, iso, sel[c][iso][0]))
            else:
                gaps.append((c, iso))
    for g in gaps:
        print("GAP (no frame near midnight in listing head):", g[0], g[1])
    print(f"jobs: {len(jobs)}")
    n_done = 0
    fails = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for job, status in ex.map(download_one, jobs):
            if status == "FAIL":
                fails.append(job)
                print(f"FAIL {job}", flush=True)
            else:
                n_done += 1
                print(f"{status} {job[0]} {job[1]} [{n_done}/{len(jobs)}]", flush=True)
    print(f"DONE ok+cached={n_done} fails={len(fails)} gaps={len(gaps)}")
    if fails:
        print("failures:", json.dumps(fails))


if __name__ == "__main__":
    main()
