#!/usr/bin/env python3
"""
Turns the CSV logs from telemetry_logger.py into numbers and figures.

    pip install -r tools/requirements.txt
    python tools/analyze_results.py

By default the newest data/static_*.csv, stairs_*.csv, tilt_*.csv,
range_*.csv, gps_*.csv and bench_*.csv are used; pass --static FILE (etc.) to pick a different run.
Current-draw readings taken with a USB power meter go in results/manual.json:

    {"supply_v": 5.0, "current_ma_streaming": 0, "current_ma_idle": 0, "battery_mah": 0}

Outputs: results/summary.json and results/fig_*.png (300 dpi, IEEE column width).
"""

import argparse
import csv
import glob
import json
import os
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")

# Expected ADXL335 output on NodeMCU A0, worked out in the paper:
# 3.3 V supply, 330 mV/g, zero-g at Vs/2, A0 full scale about 3.2 V (on-board divider).
EXPECTED_COUNTS_PER_G = 105.5
EXPECTED_ZERO_G = 527

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.grid": True, "grid.alpha": 0.3,
    "savefig.dpi": 300, "savefig.bbox": "tight",
})
COL_W = 3.45  # inches, one IEEE column


def latest(test):
    files = sorted(glob.glob(os.path.join(DATA, f"{test}_*.csv")))
    return files[-1] if files else None


def load(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r["t_s"] = float(r["t_s"])
            r["ok"] = r["ok"] == "1"
            r["rtt_ms"] = float(r["rtt_ms"])
            if r["ok"]:
                for k in ("alt_m", "pressure_hpa", "temp_c"):
                    r[k] = float(r[k])
                r["z_raw"] = int(float(r["z_raw"]))
            rows.append(r)
    return rows


def segments(rows, settle_s):
    """Split rows into runs of the same label; drop the first settle_s seconds of each run."""
    segs, cur = [], None
    for r in rows:
        if cur is None or r["label"] != cur["label"]:
            cur = {"label": r["label"], "t0": r["t_s"], "rows": []}
            segs.append(cur)
        if r["t_s"] - cur["t0"] >= settle_s:
            cur["rows"].append(r)
    return segs


def num(label):
    try:
        return float(label)
    except ValueError:
        return None


def r2(x, nd=2):
    return None if x is None else round(float(x), nd)


def link_stats(rows):
    rtt = np.array([r["rtt_ms"] for r in rows if r["ok"]])
    n = len(rows)
    ok = int(sum(r["ok"] for r in rows))
    return {
        "requests": n, "ok": ok,
        "success_pct": r2(100.0 * ok / n if n else None),
        "rtt_mean_ms": r2(rtt.mean() if len(rtt) else None, 1),
        "rtt_median_ms": r2(np.median(rtt) if len(rtt) else None, 1),
        "rtt_p95_ms": r2(np.percentile(rtt, 95) if len(rtt) else None, 1),
        "rtt_max_ms": r2(rtt.max() if len(rtt) else None, 1),
    }


# ---------------------------------------------------------------- static
def analyze_static(path):
    rows = load(path)
    ok = [r for r in rows if r["ok"]]
    t = np.array([r["t_s"] for r in ok])
    alt = np.array([r["alt_m"] for r in ok])
    pre = np.array([r["pressure_hpa"] for r in ok])
    tmp = np.array([r["temp_c"] for r in ok])
    z = np.array([r["z_raw"] for r in ok])
    dur = rows[-1]["t_s"] - rows[0]["t_s"]
    slope = np.polyfit(t, alt, 1)[0] if len(t) > 2 else 0.0
    head, tail = t < t[0] + 30, t > t[-1] - 30
    out = {
        "file": os.path.basename(path), "duration_min": r2(dur / 60, 1),
        **link_stats(rows),
        "sample_rate_hz": r2(len(ok) / dur if dur else None),
        "longest_gap_s": r2(np.diff(t).max() if len(t) > 1 else None),
        "alt_mean_m": r2(alt.mean(), 3), "alt_std_m": r2(alt.std(ddof=1), 3),
        "alt_p2p_m": r2(alt.max() - alt.min(), 3),
        "alt_drift_m_per_min": r2(slope * 60, 3),
        "pressure_std_hpa": r2(pre.std(ddof=1), 3),
        "temp_start_c": r2(tmp[head].mean()), "temp_end_c": r2(tmp[tail].mean()),
        "z_mean": r2(z.mean(), 1), "z_std": r2(z.std(ddof=1), 2), "z_p2p": int(z.max() - z.min()),
    }

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(COL_W, 2.9), sharex=True)
    a1.plot(t / 60, alt, lw=0.6, color="#1f4e79")
    a1.set_ylabel("Rel. altitude (m)")
    a2.plot(t / 60, z, lw=0.6, color="#b35c00")
    a2.set_ylabel("Z-axis (ADC counts)")
    a2.set_xlabel("Time (min)")
    fig.savefig(os.path.join(RESULTS, "fig_static.png"))
    plt.close(fig)
    return out


# ---------------------------------------------------------------- stairs
def analyze_stairs(path):
    rows = load(path)
    segs = [s for s in segments(rows, settle_s=5) if num(s["label"]) is not None and len(s["rows"]) >= 10]
    segs = [dict(s, ok=[r for r in s["rows"] if r["ok"]]) for s in segs]
    segs = [s for s in segs if len(s["ok"]) >= 10]
    if not segs:
        return None
    base_ref = num(segs[0]["label"])
    base_alt = np.mean([r["alt_m"] for r in segs[0]["ok"]])
    levels = []
    for s in segs:
        a = np.array([r["alt_m"] for r in s["ok"]])
        ref = num(s["label"]) - base_ref
        meas = a.mean() - base_alt
        levels.append({"ref_m": r2(ref), "meas_m": r2(meas), "err_m": r2(meas - ref),
                       "std_m": r2(a.std(ddof=1)), "n": len(a)})
    errs = np.array([lv["err_m"] for lv in levels[1:]]) if len(levels) > 1 else np.array([0.0])
    closure = levels[-1]["err_m"] if len(levels) > 1 and levels[-1]["ref_m"] == 0 else None
    out = {"file": os.path.basename(path), "levels": levels,
           "rmse_m": r2(np.sqrt(np.mean(errs ** 2))), "max_abs_err_m": r2(np.abs(errs).max()),
           "closure_m": closure, **link_stats(rows)}

    ok = [r for r in rows if r["ok"]]
    t = np.array([r["t_s"] for r in ok]) / 60
    alt = np.array([r["alt_m"] for r in ok]) - base_alt
    fig, ax = plt.subplots(figsize=(COL_W, 2.1))
    ax.plot(t, alt, lw=0.6, color="#1f4e79", label="Measured")
    for ref in sorted({lv["ref_m"] for lv in levels}):
        ax.axhline(ref, color="#b35c00", lw=0.6, ls="--")
    ax.plot([], [], color="#b35c00", lw=0.6, ls="--", label="Tape reference")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Height above start (m)")
    ax.legend(loc="upper left")
    fig.savefig(os.path.join(RESULTS, "fig_stairs.png"))
    plt.close(fig)
    return out


# ---------------------------------------------------------------- tilt
def analyze_tilt(path):
    rows = load(path)
    groups = {}
    for s in segments(rows, settle_s=3):
        key = s["label"].lower()
        if key in ("up", "side", "down"):
            groups.setdefault(key, []).extend(r["z_raw"] for r in s["rows"] if r["ok"])
    if not all(k in groups and len(groups[k]) >= 10 for k in ("up", "side", "down")):
        return None
    m = {k: float(np.mean(v)) for k, v in groups.items()}
    sd = {k: float(np.std(v, ddof=1)) for k, v in groups.items()}
    cpg = (m["up"] - m["down"]) / 2
    zero = (m["up"] + m["down"]) / 2
    out = {"file": os.path.basename(path),
           "up_mean": r2(m["up"], 1), "side_mean": r2(m["side"], 1), "down_mean": r2(m["down"], 1),
           "up_std": r2(sd["up"]), "side_std": r2(sd["side"]), "down_std": r2(sd["down"]),
           "counts_per_g": r2(cpg, 1), "zero_g_counts": r2(zero, 1),
           "mg_per_count": r2(1000 / cpg, 1) if cpg else None,
           "side_err_g": r2((m["side"] - zero) / cpg, 3) if cpg else None,
           "noise_mg": r2(1000 * sd["up"] / cpg, 1) if cpg else None,
           "expected_counts_per_g": EXPECTED_COUNTS_PER_G, "expected_zero_g": EXPECTED_ZERO_G,
           "sensitivity_err_pct": r2(100 * (cpg - EXPECTED_COUNTS_PER_G) / EXPECTED_COUNTS_PER_G, 1)}

    fig, ax = plt.subplots(figsize=(COL_W, 2.0))
    order = ["down", "side", "up"]
    ax.boxplot([groups[k] for k in order], widths=0.5, medianprops={"color": "#1f4e79"})
    ax.set_xticks([1, 2, 3], ["−1 g (down)", "0 g (side)", "+1 g (up)"])
    exp = [EXPECTED_ZERO_G - EXPECTED_COUNTS_PER_G, EXPECTED_ZERO_G, EXPECTED_ZERO_G + EXPECTED_COUNTS_PER_G]
    ax.plot([1, 2, 3], exp, "x", color="#b35c00", label="Expected (3.3 V)")
    ax.set_ylabel("Z-axis (ADC counts)")
    ax.legend(loc="upper left")
    fig.savefig(os.path.join(RESULTS, "fig_tilt.png"))
    plt.close(fig)
    return out


# ---------------------------------------------------------------- range
def analyze_range(path):
    rows = load(path)
    by_d = {}
    for s in segments(rows, settle_s=3):
        d = num(s["label"])
        if d is not None:
            by_d.setdefault(d, []).extend(s["rows"])
    pts = []
    for d in sorted(by_d):
        if len(by_d[d]) >= 10:
            pts.append({"d_m": r2(d, 1), **link_stats(by_d[d])})
    if not pts:
        return None
    good = [p["d_m"] for p in pts if p["success_pct"] >= 95]
    out = {"file": os.path.basename(path), "points": pts,
           "max_reliable_m": max(good) if good else None,
           "max_tested_m": pts[-1]["d_m"]}

    d = [p["d_m"] for p in pts]
    fig, ax = plt.subplots(figsize=(COL_W, 2.1))
    ax.plot(d, [p["success_pct"] for p in pts], "o-", ms=3, lw=0.8, color="#1f4e79", label="Success rate")
    ax.set_xlabel("Distance from board (m)")
    ax.set_ylabel("Requests answered (%)")
    ax.set_ylim(0, 105)
    ax2 = ax.twinx()
    ax2.plot(d, [p["rtt_median_ms"] or np.nan for p in pts], "s--", ms=3, lw=0.8, color="#b35c00", label="Median RTT")
    ax2.set_ylabel("Round-trip time (ms)")
    ax2.set_ylim(bottom=0)
    ax2.grid(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left")
    fig.savefig(os.path.join(RESULTS, "fig_range.png"))
    plt.close(fig)
    return out


def analyze_gps(path):
    """Static GPS run with the FlightDataRecorder_GPS firmware: fix time, satellites and position scatter."""
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("ok") == "1" and r.get("gps_chars")]
    if not rows:
        return None
    fixed = [r for r in rows if r.get("gps_fix") == "1" and r.get("lat")]
    out = {"file": os.path.basename(path), "samples": len(rows),
           "fix_pct": r2(100.0 * len(fixed) / len(rows), 1),
           "gps_chars_last": int(float(rows[-1]["gps_chars"]))}
    if not fixed:
        return out
    t_first = float(fixed[0]["t_s"])
    lat = np.array([float(r["lat"]) for r in fixed])
    lon = np.array([float(r["lon"]) for r in fixed])
    lat0, lon0 = lat.mean(), lon.mean()
    north = (lat - lat0) * 111320.0
    east = (lon - lon0) * 111320.0 * np.cos(np.radians(lat0))
    radial = np.hypot(north, east)
    sats = np.array([float(r["sats"]) for r in fixed])
    hdop = np.array([float(r["hdop"]) for r in fixed])
    out.update({
        "time_to_first_fix_s": r2(t_first, 1),
        "mean_lat": round(float(lat0), 6), "mean_lon": round(float(lon0), 6),
        "cep50_m": r2(np.median(radial)), "r95_m": r2(np.percentile(radial, 95)),
        "std_north_m": r2(north.std(ddof=1)), "std_east_m": r2(east.std(ddof=1)),
        "sats_mean": r2(sats.mean(), 1), "sats_min": int(sats.min()),
        "hdop_mean": r2(hdop.mean(), 2),
        "gps_alt_mean_m": r2(np.mean([float(r["gps_alt_m"]) for r in fixed]), 1),
    })

    fig, ax = plt.subplots(figsize=(COL_W, COL_W))
    ax.plot(east, north, ".", ms=2, color="#1f4e79", alpha=0.6, label="Fixes")
    for rad, name, col in ((out["cep50_m"], "CEP50", "#b35c00"), (out["r95_m"], "R95", "#5a6470")):
        ax.add_patch(plt.Circle((0, 0), rad, fill=False, ls="--", color=col, label=f"{name} = {rad:.1f} m"))
    lim = max(out["r95_m"] * 1.3, 1.0)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.legend(loc="upper right")
    fig.savefig(os.path.join(RESULTS, "fig_gps.png"))
    plt.close(fig)
    return out


def analyze_bench(path):
    """Short bench check transcribed from the dashboard's own log table (data/bench_*.csv)."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    if len(rows) < 3:
        return None
    t = [datetime.strptime(r["time"], "%H:%M:%S") for r in rows]
    alt = np.array([float(r["alt_m"]) for r in rows])
    pre = np.array([float(r["pressure_hpa"]) for r in rows])
    z = np.array([float(r["z_raw"]) for r in rows])
    z_base = float(rows[0]["z_base"])
    return {
        "file": os.path.basename(path), "n": len(rows), "duration_s": (t[-1] - t[0]).seconds,
        "alt_mean_m": r2(alt.mean(), 3), "alt_std_m": r2(alt.std(ddof=1), 3),
        "alt_min_m": r2(alt.min()), "alt_max_m": r2(alt.max()), "alt_p2p_m": r2(alt.max() - alt.min()),
        "pressure_min_hpa": r2(pre.min()), "pressure_max_hpa": r2(pre.max()),
        "pressure_p2p_hpa": r2(pre.max() - pre.min()),
        "pressure_p2p_as_m": r2((pre.max() - pre.min()) * 8.4),  # dh/dP from the paper, eq. (2)
        "temp_c": r2(float(rows[0]["temp_c"])),
        "z_flat": r2(z.mean(), 1), "z_std": r2(z.std(ddof=1), 2), "z_base": z_base,
        "z_drop": r2(z_base - z.mean(), 1), "z_drop_g": r2((z_base - z.mean()) / EXPECTED_COUNTS_PER_G, 3),
        "expected_z_flat_3v3": EXPECTED_ZERO_G + EXPECTED_COUNTS_PER_G,
        "expected_z_flat_3v0": 575,
    }


def analyze_power():
    path = os.path.join(RESULTS, "manual.json")
    if not os.path.exists(path):
        return None
    m = json.load(open(path))
    v, i = m.get("supply_v"), m.get("current_ma_streaming")
    if not v or not i:
        return None
    out = {"supply_v": v, "current_ma_streaming": i, "current_ma_idle": m.get("current_ma_idle") or None,
           "power_mw": r2(v * i, 0)}
    if m.get("battery_mah"):
        out["battery_mah"] = m["battery_mah"]
        out["runtime_h"] = r2(0.8 * m["battery_mah"] / i, 1)  # 80 % usable capacity
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for t in ("static", "stairs", "tilt", "range", "gps"):
        ap.add_argument(f"--{t}", help=f"CSV for the {t} test (default: newest data/{t}_*.csv)")
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)

    summary = {"generated": datetime.now().isoformat(timespec="seconds")}
    for name, fn in (("static", analyze_static), ("stairs", analyze_stairs),
                     ("tilt", analyze_tilt), ("range", analyze_range), ("gps", analyze_gps)):
        path = getattr(args, name) or latest(name)
        if not path:
            print(f"[{name}] no CSV found, skipped")
            continue
        res = fn(path)
        if res is None:
            print(f"[{name}] {os.path.basename(path)}: not enough labelled data, skipped")
            continue
        summary[name] = res
        print(f"[{name}] {os.path.basename(path)}")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    bench = latest("bench")
    if bench:
        res = analyze_bench(bench)
        if res:
            summary["bench"] = res
            print(f"[bench] {os.path.basename(bench)}")
            print(json.dumps(res, indent=2, ensure_ascii=False))
    power = analyze_power()
    if power:
        summary["power"] = power
        print("[power]", json.dumps(power))

    out = os.path.join(RESULTS, "summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
