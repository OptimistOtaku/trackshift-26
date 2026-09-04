"""Social title card for the TrackShift post.

One bold claim + the real confounder ladder as an inset, so it reads as analysis and not a
slogan. LinkedIn's link/image sweet spot is 1200x627; we render at 2x for crispness.

Run: python scripts/make_thumbnail.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")

COMPOUND = {"SOFT": "#d0021b", "MEDIUM": "#f5a623", "HARD": "#4a4a4a"}
INK = "#f4f4f5"       # near-white text on dark
SUBTLE = "#9aa0a6"    # muted subtitle
WARN = "#ff5a4d"      # the "faster" callout
BG = "#0e1116"        # dark card
PANEL = "#161b22"     # inset panel

ladder = pd.read_csv(os.path.join(ART, "q1_ladder_2026.csv"))
# rename specs to the deck labels
label_map = {"naive": "naive", "+fuel": "+ fuel", "+traffic": "+ traffic", "+rubber": "+ rubber"}
ladder["spec"] = ladder["spec"].map(lambda s: label_map.get(s, s))

W_PX, H_PX, DPI = 1200, 627, 200
fig = plt.figure(figsize=(W_PX / DPI, H_PX / DPI), dpi=DPI)
fig.patch.set_facecolor(BG)

# ---- left: the words ---------------------------------------------------- #
axL = fig.add_axes([0.055, 0.0, 0.52, 1.0])
axL.axis("off")
axL.set_facecolor(BG)

axL.text(0.0, 0.86, "This F1 tyre model", color=INK, fontsize=19,
         ha="left", va="center", weight="regular", transform=axL.transAxes)
axL.text(0.0, 0.745, "says worn tyres are", color=INK, fontsize=19,
         ha="left", va="center", weight="regular", transform=axL.transAxes)
axL.text(0.0, 0.60, "faster.", color=WARN, fontsize=30,
         ha="left", va="center", weight="bold", style="italic", transform=axL.transAxes)

axL.text(0.0, 0.44, "It's wrong — and that's", color=INK, fontsize=16,
         ha="left", va="center", transform=axL.transAxes)
axL.text(0.0, 0.35, "the interesting part.", color=INK, fontsize=16,
         ha="left", va="center", transform=axL.transAxes)

axL.plot([0.0, 0.12], [0.215, 0.215], color=WARN, lw=2.4, transform=axL.transAxes,
         solid_capstyle="round")
axL.text(0.0, 0.13, "PITWALL   ·   TrackShift 2026", color=SUBTLE, fontsize=11,
         ha="left", va="center", weight="bold", transform=axL.transAxes)
axL.text(0.0, 0.065, "deconfounded F1 tyre degradation", color=SUBTLE, fontsize=9.5,
         ha="left", va="center", transform=axL.transAxes)

# ---- right: the real ladder, dark-themed -------------------------------- #
# opaque panel behind the inset so the headline can never bleed under it
axP = fig.add_axes([0.60, 0.0, 0.40, 1.0], zorder=1)
axP.axis("off")
axP.add_patch(plt.Rectangle((0, 0), 1, 1, transform=axP.transAxes,
                            facecolor=PANEL, edgecolor="none"))

axR = fig.add_axes([0.655, 0.145, 0.315, 0.66], zorder=2)
axR.set_facecolor(PANEL)
for s in axR.spines.values():
    s.set_visible(False)

compounds = ["SOFT", "MEDIUM", "HARD"]
specs = ladder["spec"].tolist()
x = np.arange(len(specs))
w = 0.8 / len(compounds)
for i, c in enumerate(compounds):
    vals = ladder[f"{c}_deg10"].to_numpy()
    axR.bar(x + (i - 1) * w, vals, w, color=COMPOUND[c], label=c.title(), zorder=3)

axR.axhline(0, color=INK, lw=1.4, zorder=4)
axR.axhspan(axR.get_ylim()[0], 0, color=WARN, alpha=0.10, zorder=0)
axR.text(0.97, 0.06, "tyres get FASTER", color=WARN, fontsize=8.5, style="italic",
         ha="right", va="bottom", transform=axR.transAxes, weight="bold")

axR.set_xticks(x)
axR.set_xticklabels(specs, color=INK, fontsize=8.2)
axR.tick_params(axis="y", colors=SUBTLE, labelsize=7.5)
axR.grid(axis="y", color=SUBTLE, alpha=0.15, lw=0.6, zorder=0)
axR.set_axisbelow(True)
axR.set_title("degradation at tyre age 10 (s/lap)", color=SUBTLE, fontsize=8.5, pad=6)
leg = axR.legend(loc="upper left", fontsize=7.5, frameon=False, ncol=1,
                 labelcolor=INK, handlelength=1.1, borderpad=0.2)

out = os.path.join(ART, "thumb_hook.png")
fig.savefig(out, facecolor=BG, dpi=DPI)
plt.close(fig)
print(out)
