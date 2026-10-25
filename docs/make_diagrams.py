#!/usr/bin/env python3
"""
Draws the block diagram, circuit diagram and firmware flowchart for the
FlightDataRecorder_GPS build (BMP280 + ADXL335 Z-axis + NEO-6M GPS + ESP8266 SoftAP web server).

    python docs/make_diagrams.py

Writes docs/block_diagram.png (one IEEE column), docs/block_diagram_wide.png
(for slides), docs/circuit_diagram.png and docs/firmware_flowchart.png.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY, TEAL, ORANGE, GREY, RED, INK = "#1E3A5F", "#17868A", "#C97A12", "#5A6470", "#B83227", "#1B1F24"
PANEL = "#EEF2F6"
plt.rcParams.update({"font.family": "DejaVu Sans", "savefig.dpi": 300})


def canvas(w, h, xmax=100, ymax=100):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, color, title, body="", fs=7, tc="white", r=1.6, bfs=None, lw=0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=color, ec=INK if lw else color, lw=lw))
    if body:
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", color=tc, fontsize=fs, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.30, body, ha="center", va="center", color=tc, fontsize=bfs or fs - 1.2,
                linespacing=1.25)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", color=tc, fontsize=fs, fontweight="bold",
                linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color=INK, lw=1.0, ls="-", label=None, lx=None, ly=None, fs=6, ha="left"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls, mutation_scale=7))
    if label:
        ax.text(lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2, label,
                fontsize=fs, color=color, ha=ha, va="center", fontweight="bold")


# ------------------------------------------------------------------ block diagram (column)
def block_column():
    fig, ax = canvas(3.45, 3.55)
    ax.add_patch(FancyBboxPatch((1, 35.5), 98, 63.5, boxstyle="round,pad=0,rounding_size=2", fc=PANEL, ec="#C9D3DD", lw=0.8))
    ax.text(3, 96.6, "AIRBORNE NODE", fontsize=6.2, color=NAVY, fontweight="bold", va="center")

    box(ax, 2, 78, 22.5, 15.5, TEAL, "BMP280", "pressure,\ntemp.", fs=6.4, bfs=5.2)
    box(ax, 26.5, 78, 22.5, 15.5, TEAL, "ADXL335", "Z-axis\naccel.", fs=6.4, bfs=5.2)
    box(ax, 51, 78, 22.5, 15.5, "#2E6DA4", "NEO-6M", "GPS position,\nsatellites", fs=6.4, bfs=5.2)
    box(ax, 75.5, 78, 22.5, 15.5, ORANGE, "Power", "5 V USB /\nbank → VIN", fs=6.4, bfs=5.2)

    arrow(ax, 13.25, 78, 13.25, 66.5, label="I²C 0x76\nD2 / D1", lx=14.5, ly=72, fs=5.0)
    arrow(ax, 37.75, 78, 37.75, 66.5, label="analog\n→ A0", lx=39, ly=72, fs=5.0)
    arrow(ax, 62.25, 78, 62.25, 66.5, label="UART 9600\nD5 / D6", lx=63.5, ly=72, fs=5.0)
    arrow(ax, 86.75, 78, 86.75, 66.5, color=ORANGE, label="5 V →\n3.3 V", lx=88, ly=72, fs=5.0)

    ax.add_patch(FancyBboxPatch((3, 38), 94, 28.5, boxstyle="round,pad=0,rounding_size=1.8", fc=NAVY, ec=NAVY))
    ax.text(50, 62.3, "ESP8266 NodeMCU (ESP-12E, 80 MHz)", ha="center", va="center", color="white", fontsize=7, fontweight="bold")
    ax.text(50, 57.8, "SoftAP  “VIT-Telemetry”  ·  192.168.4.1", ha="center", va="center", color="#BFD3E6", fontsize=5.8)
    for i, (t, b) in enumerate([("Boot", "P₀ and Z₀\nreference"), ("GPS", "TinyGPSPlus\nNMEA → fix"),
                                 ("HTTP :80", "GET /\nGET /data"), ("Flash", "9.2 kB page\nPROGMEM")]):
        box(ax, 5 + i * 23, 40.5, 21, 14, "#2E5A87", t, b, fs=6.0, bfs=5.0, r=1.2)

    arrow(ax, 50, 38, 50, 25.5, color="#2E6DA4", ls="--", lw=1.1)
    ax.text(52, 31.8, "802.11 b/g/n link\nHTTP poll every 500 ms\n~200-byte JSON reply", fontsize=5.4, color="#2E6DA4",
            va="center", fontweight="bold")

    ax.add_patch(FancyBboxPatch((1, 1), 98, 25, boxstyle="round,pad=0,rounding_size=2", fc="#FBF3E8", ec="#EBCB9C", lw=0.8))
    ax.text(3, 23, "CLIENT DEVICES (no app, no internet)", fontsize=6.2, color=ORANGE, fontweight="bold", va="center")
    box(ax, 3, 3, 46, 16.5, ORANGE, "Phone / laptop browser", "live values · altitude\nwaveform · log table", fs=6.4, bfs=5.4)
    box(ax, 51, 3, 46, 16.5, GREY, "Python test logger", "CSV per test →\nstats and figures", fs=6.4, bfs=5.4)
    fig.savefig(os.path.join(HERE, "block_diagram.png"))
    plt.close(fig)


# ------------------------------------------------------------------ block diagram (wide, slides)
def block_wide():
    fig, ax = canvas(11, 5.0, 110, 50)
    ax.add_patch(FancyBboxPatch((1, 1), 70, 48, boxstyle="round,pad=0,rounding_size=1.5", fc=PANEL, ec="#C9D3DD", lw=1))
    ax.text(3, 46.5, "AIRBORNE NODE", fontsize=11, color=NAVY, fontweight="bold", va="center")
    for i, (t, b, col) in enumerate([("BMP280", "pressure · temperature", TEAL), ("ADXL335", "Z-axis acceleration", TEAL),
                                      ("NEO-6M GPS", "position · satellites", "#2E6DA4"), ("Power", "5 V USB / bank → VIN", ORANGE)]):
        box(ax, 3, 35 - i * 9.5, 21, 8.6, col, t, b, fs=12, bfs=9.5, r=1.0)
    for i, (lab, col) in enumerate([("I²C (D2/D1)", INK), ("analog → A0", INK), ("UART (D5/D6)", INK), ("5 V → VIN", ORANGE)]):
        y = 39.3 - i * 9.5
        arrow(ax, 24, y, 36, y, lw=1.4, color=col, label=lab, lx=25, ly=y + 2, fs=9)

    ax.add_patch(FancyBboxPatch((36, 4), 33, 38, boxstyle="round,pad=0,rounding_size=1.2", fc=NAVY, ec=NAVY))
    ax.text(52.5, 38.5, "ESP8266 NodeMCU", ha="center", color="white", fontsize=13, fontweight="bold", va="center")
    ax.text(52.5, 35, "ESP-12E · 80 MHz · SoftAP 192.168.4.1", ha="center", color="#BFD3E6", fontsize=9, va="center")
    for i, (t, b) in enumerate([("Boot calibration", "P₀ and Z₀ references"), ("GPS parser", "TinyGPSPlus: NMEA → fix"),
                                 ("HTTP server :80", "GET /   ·   GET /data"), ("Dashboard in flash", "9.2 kB page (PROGMEM)")]):
        box(ax, 38.5, 26.8 - i * 7.2, 28, 6.6, "#2E5A87", t, b, fs=9.5, bfs=8, r=0.8)

    arrow(ax, 69, 23, 79, 23, color="#2E6DA4", ls="--", lw=1.8)
    ax.text(74, 28.5, "Wi-Fi\nHTTP\n2 Hz", fontsize=9, color="#2E6DA4", ha="center", va="center", fontweight="bold")

    ax.add_patch(FancyBboxPatch((79, 1), 30, 48, boxstyle="round,pad=0,rounding_size=1.5", fc="#FBF3E8", ec="#EBCB9C", lw=1))
    ax.text(81, 46.5, "CLIENT DEVICES", fontsize=11, color=ORANGE, fontweight="bold", va="center")
    box(ax, 81, 24, 26, 18, ORANGE, "Phone / laptop browser", "live values\naltitude waveform\nlog table", fs=11, bfs=9.5, r=1.2)
    box(ax, 81, 4, 26, 16, GREY, "Python test logger", "CSV per test\n→ stats + figures", fs=11, bfs=9.5, r=1.2)
    fig.savefig(os.path.join(HERE, "block_diagram_wide.png"))
    plt.close(fig)


# ------------------------------------------------------------------ circuit diagram
def circuit():
    fig, ax = canvas(3.45, 2.75, 100, 80)
    fs = 5.6

    def chip(x, y, w, h, color, name, sub, pins, side="right"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=color, ec=color))
        ax.text(x + w / 2, y + h - 3.2, name, ha="center", color="white", fontsize=6.6, fontweight="bold", va="center")
        ax.text(x + w / 2, y + h - 7.2, sub, ha="center", color="#E3EEF2", fontsize=4.9, va="center")
        pos = {}
        for label, py in pins:
            px = x + w if side == "right" else x
            ax.text(px - 1.2 if side == "right" else px + 1.2, py, label, ha="right" if side == "right" else "left",
                    va="center", fontsize=fs, color="white", fontweight="bold")
            pos[label] = (px, py)
        return pos

    bmp = chip(2, 42, 21, 35, TEAL, "BMP280", "I²C addr 0x76",
               [("VCC", 61), ("GND", 56), ("SCL", 51), ("SDA", 47.5)])
    adx = chip(2, 6, 21, 31, TEAL, "ADXL335", "Z only (X, Y n.c.)",
               [("VCC", 22), ("GND", 16), ("Z", 10)])
    mcu = chip(58, 6, 24, 71, NAVY, "NodeMCU", "ESP8266 ESP-12E",
               [("3V3", 61), ("GND", 56), ("D1", 51), ("D2", 47.5), ("A0", 10)], side="left")
    for lab, py in (("3V3", 61), ("GND", 56), ("D5", 51), ("D6", 46)):
        ax.text(80.8, py, lab, ha="right", va="center", fontsize=fs, color="white", fontweight="bold")
    ax.text(70, 31, "GPIO5 = SCL\nGPIO4 = SDA\nA0: 10-bit ADC\n(0–3.2 V via\non-board divider)",
            ha="center", va="center", color="#BFD3E6", fontsize=4.7, linespacing=1.3)
    ax.text(70, 15.8, "VIN", ha="center", va="center", color="white", fontsize=fs, fontweight="bold")

    # nets: 3V3 (red), GND (black), SCL, SDA, Z
    def net(points, color, lw=0.9):
        xs, ys = zip(*points)
        ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round")

    def dot(x, y, color):
        ax.plot([x], [y], "o", ms=2.2, color=color)

    rail_3v3, rail_gnd = 31, 35
    net([bmp["VCC"], (rail_3v3, 61)], RED); net([adx["VCC"], (rail_3v3, 22)], RED)
    net([(rail_3v3, 22), (rail_3v3, 61), mcu["3V3"]], RED); dot(rail_3v3, 61, RED)
    net([bmp["GND"], (rail_gnd, 56)], INK); net([adx["GND"], (rail_gnd, 16)], INK)
    net([(rail_gnd, 16), (rail_gnd, 56), mcu["GND"]], INK); dot(rail_gnd, 56, INK)
    net([bmp["SCL"], mcu["D1"]], "#2E6DA4")
    net([bmp["SDA"], mcu["D2"]], "#7FB2DD")
    net([adx["Z"], mcu["A0"]], ORANGE)
    ax.text(46, 52.8, "SCL", fontsize=fs - 0.4, color="#2E6DA4", ha="center", fontweight="bold")
    ax.text(46, 44.8, "SDA", fontsize=fs - 0.4, color="#5E93C2", ha="center", fontweight="bold")
    ax.text(46, 11.8, "Z out (analog)", fontsize=fs - 0.4, color=ORANGE, ha="center", fontweight="bold")
    ax.text(rail_3v3 - 1, 66, "3.3 V", fontsize=fs - 0.4, color=RED, ha="center", fontweight="bold")
    ax.text(rail_gnd + 1.5, 66, "GND", fontsize=fs - 0.4, color=INK, ha="center", fontweight="bold")
    net([(rail_3v3, 61), (rail_3v3, 64)], RED); net([(rail_gnd, 56), (rail_gnd, 64)], INK)

    gps_pins = chip(87, 39, 12, 37, "#2E6DA4", "NEO-6M", "GPS6MV2",
                    [("VCC", 61), ("GND", 56), ("TX", 51), ("RX", 46)], side="left")
    net([(82, 61), gps_pins["VCC"]], RED)
    net([(82, 56), gps_pins["GND"]], INK)
    net([(82, 51), gps_pins["TX"]], "#3F8F5A")
    net([(82, 46), gps_pins["RX"]], "#7DBE8E")
    ax.text(93, 33.5, "TX→D5\nRX→D6", fontsize=4.6, color="#3F8F5A", ha="center", va="center", fontweight="bold")

    ax.add_patch(FancyBboxPatch((86, 9), 12.5, 14, boxstyle="round,pad=0,rounding_size=1", fc=ORANGE, ec=ORANGE))
    ax.text(92.2, 16, "5 V\nUSB /\nbank", ha="center", va="center", color="white", fontsize=5.2, fontweight="bold")
    arrow(ax, 86, 16, 82, 16, color=ORANGE)
    fig.savefig(os.path.join(HERE, "circuit_diagram.png"))
    plt.close(fig)


# ------------------------------------------------------------------ firmware flowchart
def flowchart():
    fig, ax = canvas(3.45, 3.6, 100, 104)
    fs = 5.5

    def step(x, y, w, h, text, color=NAVY, tc="white"):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=color, ec=color))
        ax.text(x, y, text, ha="center", va="center", color=tc, fontsize=fs, linespacing=1.2)

    def decision(x, y, w, h, text):
        ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True, fc=ORANGE, ec=ORANGE))
        ax.text(x, y, text, ha="center", va="center", color="white", fontsize=fs - 0.2, fontweight="bold", linespacing=1.1)

    def down(x, y1, y2):
        arrow(ax, x, y1, x, y2, lw=0.8)

    ax.text(24, 101.5, "setup()  — runs once", ha="center", fontsize=6, color=NAVY, fontweight="bold")
    ax.text(76, 101.5, "loop()  — runs forever", ha="center", fontsize=6, color=NAVY, fontweight="bold")
    ax.plot([50, 50], [2, 103], color="#C9D3DD", lw=0.8, ls=":")

    L = 24
    step(L, 94.5, 44, 8, "Power on · Serial 115200\nGPS serial 9600 (D5/D6)", GREY)
    down(L, 90.5, 88.5)
    step(L, 85, 44, 7, "Wire.begin(SDA = GPIO4,\nSCL = GPIO5)")
    down(L, 81.5, 78)
    decision(L, 71.5, 30, 13, "BMP280\nat 0x76?")
    step(L - 12, 56.5, 22, 10, "Average 20\nreadings → P₀", TEAL)
    step(L + 13, 56.5, 22, 10, "bmpFound =\nfalse (zeros)", "#8A949E")
    arrow(ax, L - 8, 66.5, L - 12, 61.5, lw=0.8); ax.text(L - 15, 65.5, "yes", fontsize=fs - 0.5, color=INK)
    arrow(ax, L + 8, 66.5, L + 13, 61.5, lw=0.8); ax.text(L + 13.5, 65.5, "no", fontsize=fs - 0.5, color=INK)
    arrow(ax, L - 12, 51.5, L - 3, 46, lw=0.8); arrow(ax, L + 13, 51.5, L + 3, 46, lw=0.8)
    step(L, 41.5, 44, 8, "Average 20 A0 readings\n→ Z₀ baseline", TEAL)
    down(L, 37.5, 34)
    step(L, 28.5, 44, 10, "Start SoftAP “VIT-Telemetry”\nregister  /  and  /data\nserver.begin()")
    down(L, 23.5, 20)
    step(L, 15.5, 36, 8, "Dashboard ready\n(192.168.4.1)", GREY)
    arrow(ax, L + 18, 15.5, 58, 15.5, lw=0.8)

    R = 73
    step(R, 15.5, 36, 8, "feedGPS(), then\nserver.handleClient()", NAVY)
    arrow(ax, R, 19.5, R, 26, lw=0.8)
    decision(R, 34, 32, 15, "request\nreceived?")
    ax.text(R + 14.5, 26.5, "no", fontsize=fs - 0.5, color=INK)
    ax.annotate("", xy=(R + 18, 15.5), xytext=(R + 16, 34),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8, mutation_scale=7, connectionstyle="angle,angleA=0,angleB=90,rad=0"))
    down(R, 41.5, 47)
    ax.text(R + 1.5, 44, "yes", fontsize=fs - 0.5, color=INK)
    decision(R, 54, 32, 13, "path?")
    step(R - 11, 72, 21, 12, "GET /\nsend 9.2 kB\npage from flash", TEAL)
    step(R + 12, 74, 20, 22, "GET /data\nread P, T, h,\nA0 + GPS fix\n→ JSON\n(~200 bytes)", TEAL)
    arrow(ax, R - 6, 59, R - 12, 66, lw=0.8); arrow(ax, R + 6, 59, R + 12, 63, lw=0.8)
    ax.annotate("", xy=(R + 18, 12.5), xytext=(R + 22, 74),
                arrowprops=dict(arrowstyle="-|>", color=GREY, lw=0.7, ls="--", mutation_scale=6,
                                connectionstyle="angle,angleA=-90,angleB=0,rad=0"))
    ax.text(R + 12, 89, "browser polls /data\nevery 500 ms", ha="center", fontsize=fs - 0.6, color=GREY, style="italic")
    fig.savefig(os.path.join(HERE, "firmware_flowchart.png"))
    plt.close(fig)


if __name__ == "__main__":
    block_column()
    block_wide()
    circuit()
    flowchart()
    print("diagrams written to", HERE)
