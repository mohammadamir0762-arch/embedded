#!/usr/bin/env python3
"""Create deterministic simulated test logs when physical hardware is unavailable.

The output uses telemetry_logger.py's CSV schema so analyze_results.py and the
paper/slide builders can use it unchanged.  These are explicitly simulated
measurements; replace them with real logger files before making hardware claims.
"""

import csv
import json
import math
import os
import random
from datetime import datetime, timedelta


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")
FIELDS = ["time_iso", "t_s", "label", "ok", "rtt_ms", "alt_m", "pressure_hpa",
          "temp_c", "z_raw", "z_base", "bmp_found", "error"]
STAMP = "20261025_140000"
START = datetime(2026, 10, 25, 14, 0, 0)


def pressure(alt):
    return 1004.74 * pow(1 - alt / 44330.0, 5.255)


def write_rows(name, rows):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"{name}_{STAMP}_SIMULATED.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def row(t, label, ok=True, alt=0.0, z=577, rtt=22.0):
    out = {
        "time_iso": (START + timedelta(seconds=t)).isoformat(timespec="milliseconds"),
        "t_s": f"{t:.3f}", "label": label, "ok": int(ok), "rtt_ms": f"{rtt:.1f}",
        "alt_m": "", "pressure_hpa": "", "temp_c": "", "z_raw": "", "z_base": "",
        "bmp_found": "", "error": "" if ok else "TimeoutError",
    }
    if ok:
        out.update(alt_m=f"{alt:.3f}", pressure_hpa=f"{pressure(alt):.2f}",
                   temp_c="24.30", z_raw=str(int(round(z))), z_base="581", bmp_found="1")
    return out


def static_log(rng):
    rows = []
    for n in range(1201):
        t = n * 0.5
        alt = 0.015 * math.sin(t / 40) + 0.00022 * t + rng.gauss(0, 0.035)
        z = 577 + rng.gauss(0, 0.8)
        rows.append(row(t, "", True, alt, z, 18 + abs(rng.gauss(0, 3))))
    return rows


def stairs_log(rng):
    rows, t = [], 0.0
    # Ground floor, climb, first floor, descent, closing ground-floor check.
    for label, duration, target in (("0", 60, 0.0), ("move", 20, 1.5),
                                    ("3.20", 60, 3.08), ("move", 20, 1.5), ("0", 60, 0.09)):
        for _ in range(int(duration / 0.5)):
            alt = target + 0.025 * math.sin(t / 13) + rng.gauss(0, 0.035)
            rows.append(row(t, label, True, alt, 577 + rng.gauss(0, 0.8), 20 + abs(rng.gauss(0, 3))))
            t += 0.5
    return rows


def tilt_log(rng):
    rows, t = [], 0.0
    for label, centre in (("up", 577), ("side", 526), ("down", 474)):
        for _ in range(40):
            rows.append(row(t, label, True, rng.gauss(0, 0.025), centre + rng.gauss(0, 1.1),
                            19 + abs(rng.gauss(0, 2))))
            t += 0.5
    return rows


def range_log(rng):
    rows, t = [], 0.0
    # Probability and latency emulate a clear-line ESP8266 SoftAP range sweep.
    conditions = ((5, 1.00, 19), (10, 1.00, 22), (20, 0.99, 30),
                  (30, 0.97, 51), (40, 0.88, 180), (50, 0.30, 600))
    for distance, prob, latency in conditions:
        for _ in range(80):
            ok = rng.random() < prob
            rows.append(row(t, str(distance), ok, rng.gauss(0, 0.05), 577 + rng.gauss(0, 1),
                            latency + abs(rng.gauss(0, latency * 0.18))))
            t += 0.5
    return rows


def main():
    rng = random.Random(20261025)
    outputs = {
        "static": write_rows("static", static_log(rng)),
        "stairs": write_rows("stairs", stairs_log(rng)),
        "tilt": write_rows("tilt", tilt_log(rng)),
        "range": write_rows("range", range_log(rng)),
    }
    os.makedirs(RESULTS, exist_ok=True)
    manual = {
        "source": "SIMULATED — replace with an inline USB power-meter reading when available",
        "supply_v": 5.0, "current_ma_streaming": 118,
        "current_ma_idle": 79, "battery_mah": 10000,
    }
    with open(os.path.join(RESULTS, "manual.json"), "w") as f:
        json.dump(manual, f, indent=2)
    print("Created simulated telemetry logs:")
    for path in outputs.values():
        print(path)


if __name__ == "__main__":
    main()
