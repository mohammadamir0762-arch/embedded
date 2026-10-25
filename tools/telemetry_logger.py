#!/usr/bin/env python3
"""
Telemetry logger for the ESP8266 Flight Data Recorder.

Connect your laptop to the board's Wi-Fi ("VIT-Telemetry" / "telemetry123"),
then run one test at a time:

    python tools/telemetry_logger.py --test static --minutes 10
    python tools/telemetry_logger.py --test stairs
    python tools/telemetry_logger.py --test tilt
    python tools/telemetry_logger.py --test range
    python tools/telemetry_logger.py --test gps --minutes 10   (FlightDataRecorder_GPS firmware)

While it runs, type a label and press Enter to tag the rows that follow
(for example a tape-measured height "3.05", an orientation "up", or a
distance "20"). Type "move" while you are walking between positions.
Press Ctrl+C to stop. Each run is saved to data/<test>_<date>_<time>.csv.

Only the Python standard library is used, so nothing has to be installed.
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
import urllib.request
from datetime import datetime

FIELDS = ["time_iso", "t_s", "label", "ok", "rtt_ms", "alt_m", "pressure_hpa",
          "temp_c", "z_raw", "z_base", "bmp_found", "error",
          "gps_chars", "gps_fix", "lat", "lon", "sats", "hdop", "gps_alt_m", "speed_kmph"]

HINTS = {
    "static": "Leave the board still on a table. No labels needed.",
    "stairs": "Type the tape-measured height in metres at each landing (start with 0), "
              "'move' while climbing, and finish back at 0.",
    "tilt":   "Type 'up' (flat, chip facing up), 'side' (standing on its edge) and "
              "'down' (upside down). Hold each for about 20 s.",
    "range":  "Type the distance in metres at each stop (e.g. 5, 10, 20 ...), 'move' "
              "while walking. Hold each stop for about 60 s.",
    "gps":    "Put the board still with a clear view of the sky (outdoors or at an open window). "
              "No labels needed. Start the logger right after powering the board to measure time to first fix.",
}


def read_labels(state):
    """Background thread: every line typed on the console becomes the current label."""
    for line in sys.stdin:
        state["label"] = line.strip()
        print(f"  -> label set to '{state['label']}'")


def poll_once(url, timeout):
    """One GET /data request. Returns (ok, rtt_ms, payload or None, error text)."""
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
        rtt = (time.perf_counter() - start) * 1000.0
        return True, rtt, json.loads(body), ""
    except Exception as exc:  # timeouts, refused connections, bad JSON
        rtt = (time.perf_counter() - start) * 1000.0
        return False, rtt, None, type(exc).__name__


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", required=True, choices=sorted(HINTS))
    ap.add_argument("--url", default="http://192.168.4.1/data")
    ap.add_argument("--period", type=float, default=0.5, help="seconds between requests (dashboard uses 0.5)")
    ap.add_argument("--timeout", type=float, default=1.0, help="request timeout in seconds")
    ap.add_argument("--minutes", type=float, default=0, help="stop automatically after this many minutes")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.abspath(os.path.join(args.outdir, f"{args.test}_{stamp}.csv"))

    state = {"label": ""}
    threading.Thread(target=read_labels, args=(state,), daemon=True).start()

    print(f"Logging '{args.test}' from {args.url} every {args.period:.2f} s")
    print(HINTS[args.test])
    print(f"Saving to {path}\nPress Ctrl+C to stop.\n")

    t0 = time.perf_counter()
    next_tick = t0
    n_ok = n_fail = 0
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        try:
            while True:
                now = time.perf_counter()
                if args.minutes and now - t0 >= args.minutes * 60:
                    break
                ok, rtt, d, err = poll_once(args.url, args.timeout)
                row = {
                    "time_iso": datetime.now().isoformat(timespec="milliseconds"),
                    "t_s": f"{now - t0:.3f}",
                    "label": state["label"],
                    "ok": int(ok),
                    "rtt_ms": f"{rtt:.1f}",
                    "error": err,
                }
                if ok:
                    n_ok += 1
                    row.update(alt_m=d.get("alt"), pressure_hpa=d.get("pre"), temp_c=d.get("tmp"),
                               z_raw=d.get("zRaw"), z_base=d.get("zBase"), bmp_found=int(bool(d.get("bmpFound"))))
                    if "gpsChars" in d:  # only the GPS firmware sends these
                        row.update(gps_chars=d.get("gpsChars"), gps_fix=int(bool(d.get("gpsFix"))),
                                   lat=d.get("lat"), lon=d.get("lon"), sats=d.get("sats"), hdop=d.get("hdop"),
                                   gps_alt_m=d.get("gpsAlt"), speed_kmph=d.get("speed"))
                else:
                    n_fail += 1
                writer.writerow(row)
                f.flush()

                total = n_ok + n_fail
                if total % 20 == 0:
                    last = f"alt {d['alt']:+.2f} m  z {d['zRaw']}" if ok else f"FAILED ({err})"
                    if ok and "gpsChars" in d:
                        last += f"  gps {'FIX' if d.get('gpsFix') else 'no fix'} sats {d.get('sats')}"
                    print(f"[{now - t0:7.1f} s] {total} requests, {100.0 * n_ok / total:.1f}% ok | {last}")

                # Fixed-rate schedule; if a request overran, start the next one immediately.
                next_tick += args.period
                time.sleep(max(0.0, next_tick - time.perf_counter()))
                if time.perf_counter() - next_tick > args.period:
                    next_tick = time.perf_counter()
        except KeyboardInterrupt:
            pass

    total = n_ok + n_fail
    print(f"\nStopped. {total} requests, {n_ok} ok, {n_fail} failed. Saved {path}")


if __name__ == "__main__":
    main()
