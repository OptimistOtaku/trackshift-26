"""Charts for the deck.

House style: light background, one idea per figure, readable when projected. Every figure is
built from the same fitted objects the numbers in the write-up come from, so a chart cannot
drift out of step with the text.

The figures follow the evidence chain rather than a pitch: the confounders are removable
(fig 1-2), the resulting curve still does not transfer (fig 3-4), and what actually predicts
the value of a stop is measured elsewhere (fig 5-6).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .degradation import Fit

COMPOUND_COLOUR = {"SOFT": "#d0021b", "MEDIUM": "#f5a623", "HARD": "#4a4a4a"}
ACCENT = "#0b6ea8"
WARN = "#c0392b"
GOOD = "#1a7f4b"
MUTED = "#8a8a8a"


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 170,
        "font.size": 10.5,
        "axes.titlesize": 12.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def _save(fig, path: str) -> str:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ------------------------------------------------------------------------- #
# 1. the confounders are removable, and ignoring them inverts the answer
# ------------------------------------------------------------------------- #

def fig_ladder(ladder: pd.DataFrame, path: str, *, age: int = 10) -> str:
    """Degradation at a fixed tyre age under each specification.

    The point is the sign: the naive fit reports two of three compounds getting FASTER as
    they age. That is not a small bias to be noted in a limitations section, it is a wrong
    answer to the question that was asked.
    """
    style()
    compounds = [c.replace(f"_deg{age}", "") for c in ladder.columns
                 if c.endswith(f"_deg{age}")]
    specs = ladder["spec"].str.strip().tolist()
    x = np.arange(len(specs))
    w = 0.8 / max(len(compounds), 1)

    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    for i, c in enumerate(compounds):
        v = ladder[f"{c}_deg{age}"].to_numpy(float)
        ax.bar(x + i * w - 0.4 + w / 2, v, w * 0.92,
               label=c.title(), color=COMPOUND_COLOUR.get(c, ACCENT))

    ax.axhline(0, color="black", lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(specs)
    ax.set_ylabel(f"degradation at tyre age {age}  (s/lap)")
    ax.set_title("Ignore the confounders and the answer comes out backwards")
    ax.legend(title="compound", ncols=3, loc="upper left")

    vals = ladder[[f"{c}_deg{age}" for c in compounds]].to_numpy(float)
    lo = float(np.nanmin(vals))
    if lo < 0:
        ax.axhspan(lo * 1.15, 0, color=WARN, alpha=0.06, zorder=0)
        ax.annotate("below this line the model claims\ntyres get FASTER as they age",
                    xy=(len(specs) - 0.55, lo * 0.55), fontsize=9, color=WARN,
                    va="center", ha="center")
    return _save(fig, path)


# ------------------------------------------------------------------------- #
# 2. why track evolution is identified at all
# ------------------------------------------------------------------------- #

def fig_identification(evo_slopes: pd.DataFrame, path: str) -> str:
    """Within-run slope of the rubber regressor, by session.

    Tyre age advances at exactly 1 lap per lap in every run. Rubber does not: an FP1 run
    sees an order of magnitude more track evolution per lap than an FP3 run, because the log
    saturates. That difference in shape is the identifying variation - without it the two
    effects are collinear and no amount of data separates them.
    """
    style()
    d = evo_slopes.sort_values("order")
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.bar(d["Session"], d["median"], 0.6, color=ACCENT)
    ax.axhline(1.0, color=WARN, lw=1.6, ls="--")
    ax.annotate("tyre age, for comparison: 1.0 per lap in every run",
                xy=(0.02, 1.0), xytext=(0.02, 1.06), fontsize=9.5, color=WARN)
    for xi, (_, r) in enumerate(d.iterrows()):
        ax.text(xi, r["median"], f" {r['median']:.3f}", ha="center", va="bottom",
                fontsize=9.5)
    ax.set_ylabel("rubber regressor,\nchange per lap within a run")
    ax.set_title("Rubber is separable from tyre age only because it saturates")
    return _save(fig, path)


# ------------------------------------------------------------------------- #
# 3. the central empirical claim: the step does not depend on tyre age
# ------------------------------------------------------------------------- #

def fig_age_null(stops: pd.DataFrame, age_stats: dict, path: str) -> str:
    """Observed pit-stop step against the age of the tyre that came off.

    This is the figure the project turns on, and it is also the figure that corrected us. A
    straight line through this cloud is flat (p=0.58), which invites the headline "tyre age
    does not matter". The binned means show why that is wrong: the relationship rises to
    about age 21-25 and then turns over, so a linear fit averages a real effect to zero.
    Both are drawn, because the contrast is the finding.
    """
    style()
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    a = stops["age_old"].to_numpy(float)
    y = stops["step_obs"].to_numpy(float)
    ax.scatter(a, y, s=24, alpha=0.42, color=ACCENT, edgecolor="none",
               label=f"{age_stats['n']} stops, 12 events")

    bins = np.arange(0, a.max() + 6, 6.0)
    idx = np.digitize(a, bins)
    bx, by = [], []
    for b in np.unique(idx):
        m = idx == b
        if m.sum() >= 8:
            bx.append(a[m].mean())
            by.append(y[m].mean())
    ax.plot(bx, by, "o-", color="#111", lw=2.2, ms=6.5, label="binned mean")

    lo, hi = age_stats["age_range"]
    xs = np.linspace(lo, hi, 100)
    ax.axhline(age_stats["mean_step_s"], color=MUTED, lw=1.8, ls=":",
               label=f"season mean {age_stats['mean_step_s']:+.2f} s")
    ax.plot(xs, age_stats["mean_step_s"] + age_stats["lin_slope"] * (xs - a.mean()),
            color=WARN, lw=2.2, ls="--",
            label=f"linear fit (p={age_stats['lin_p']:.2f}) — finds nothing")

    peak = age_stats.get("peak_age", np.nan)
    if np.isfinite(peak):
        ax.axvline(peak, color=GOOD, lw=1.6, ls="-.", alpha=0.8)
        ax.annotate(f"peaks at age {peak:.0f}", xy=(peak, ax.get_ylim()[1] * 0.86),
                    xytext=(peak + 3, ax.get_ylim()[1] * 0.86), fontsize=9.5, color=GOOD)

    ax.set_xlabel("age of the tyre that came off (laps)")
    ax.set_ylabel("pace gained by fitting a new tyre (s/lap)")
    ax.set_title("Degradation accumulates for ~20 laps, then stops — not forever")
    ax.annotate(f"linear:     {age_stats['lin_slope']:+.4f} s/lap, p = {age_stats['lin_p']:.2f}\n"
                f"quadratic:  age p<0.001, age$^2$ p<0.001, joint p = {age_stats['joint_p']:.3f}",
                xy=(0.97, 0.04), xycoords="axes fraction", ha="right", fontsize=9.5,
                bbox=dict(boxstyle="round,pad=0.45", fc="#f4f4f4", ec="#cccccc"))
    ax.legend(loc="upper left", fontsize=9)
    return _save(fig, path)


# ------------------------------------------------------------------------- #
# 4. the practice curve does not transfer
# ------------------------------------------------------------------------- #

def fig_transfer_failure(stops: pd.DataFrame, pred: np.ndarray, calib: float,
                         path: str) -> str:
    """Practice-fitted prediction against the observed step.

    The level is roughly right, which is what makes this failure easy to miss. The
    calibration slope is what gives it away: the curve cannot tell a valuable stop from a
    worthless one.
    """
    style()
    obs = stops["step_obs"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(6.8, 6.0))
    lim = [min(pred.min(), obs.min()) - 0.3, max(pred.max(), obs.max()) + 0.3]
    ax.scatter(pred, obs, s=26, alpha=0.55, color=WARN, edgecolor="none")
    ax.plot(lim, lim, color="black", lw=1.2, ls="--", label="perfect calibration (slope 1.0)")

    p = pred - pred.mean()
    xs = np.linspace(lim[0], lim[1], 50)
    ax.plot(xs, obs.mean() + calib * (xs - pred.mean()), color=ACCENT, lw=2.2,
            label=f"actual fit (slope {calib:+.3f})")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("predicted by the deconfounded practice curve (s)")
    ax.set_ylabel("observed step across the stop (s)")
    ax.set_title("Right on average, uncorrelated stop by stop")
    ax.annotate(f"mean predicted {pred.mean():+.2f} s\n"
                f"mean observed  {obs.mean():+.2f} s",
                xy=(0.03, 0.93), xycoords="axes fraction", va="top", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.45", fc="#f4f4f4", ec="#cccccc"))
    ax.legend(loc="lower right")
    return _save(fig, path)


# ------------------------------------------------------------------------- #
# 5. what does predict the value of a stop
# ------------------------------------------------------------------------- #

def fig_ablation(ab: pd.DataFrame, path: str) -> str:
    """Out-of-sample gain over the season mean, by specification.

    Leave-one-event-out with no free constants, so a bar above zero means the spec found
    structure that generalises to an event it never saw.
    """
    style()
    d = ab.copy()
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    colours = []
    for s in d["spec"]:
        if s.startswith("PITWALL"):
            colours.append(GOOD)
        elif "tyre age" in s:
            colours.append(WARN)
        elif s == "mean only":
            colours.append(MUTED)
        else:
            colours.append(ACCENT)
    ax.bar(range(len(d)), d["vs_mean_pct"], 0.62, color=colours)
    for xi, (v, c) in enumerate(zip(d["vs_mean_pct"], d["calib_slope"])):
        ax.text(xi, v, f" {v:+.1f}%\ncalib {c:+.2f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9)
    ax.axhline(0, color="black", lw=1.2)
    ax.set_xticks(range(len(d)))
    ax.set_xticklabels([s.replace(" (", "\n(") for s in d["spec"]], fontsize=9.5)
    ax.set_ylabel("RMSE improvement vs season mean (%)")
    ax.set_title("What predicts the value of a stop — and what does not")
    ax.annotate("adding tyre age makes it worse",
                xy=(len(d) - 1, d["vs_mean_pct"].iloc[-1]), xytext=(len(d) - 1.5, -6.0),
                fontsize=9.5, color=WARN, ha="center",
                arrowprops=dict(arrowstyle="->", color=WARN, lw=1.2))
    ax.set_ylim(min(-9.0, d["vs_mean_pct"].min() - 4), d["vs_mean_pct"].max() + 6)
    return _save(fig, path)


def fig_per_event(pe: pd.DataFrame, path: str) -> str:
    """Per-event RMSE, model against the mean baseline.

    Reported because the pooled gain is weighted by stop count, so it is carried by the
    larger events. The event-by-event picture is the less flattering one and belongs in the
    deck next to the headline.
    """
    style()
    d = pe.sort_values("round")
    x = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    ax.bar(x - 0.19, d["rmse_s_mean"], 0.38, label="season mean", color=MUTED)
    ax.bar(x + 0.19, d["rmse_s_pitwall"], 0.38, label="PITWALL", color=GOOD)
    ax.set_xticks(x)
    ax.set_xticklabels([f"R{int(r):02d}\nn={int(n)}"
                        for r, n in zip(d["round"], d["n_pitwall"])], fontsize=9)
    ax.set_ylabel("held-out RMSE (s)")
    wins = int(d["pitwall_wins"].sum())
    ax.set_title(f"Held-out accuracy by event — PITWALL wins {wins} of {len(d)}")
    ax.legend()
    return _save(fig, path)


# ------------------------------------------------------------------------- #
# 6. the traffic measurement is real - independent falsification
# ------------------------------------------------------------------------- #

def fig_traffic_validation(by_pos: pd.DataFrame, path: str) -> str:
    """Traffic exposure against track position.

    Nothing in the traffic computation ever sees running order, so this is a genuine
    falsification test: if the measurement is real, cars further back must spend more of the
    lap in dirty air. It is the one place we can check a measured covariate against a fact
    we never gave the model.
    """
    style()
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.bar(by_pos.index.astype(str), by_pos["frac_near"], 0.6, color=ACCENT)
    for xi, v in enumerate(by_pos["frac_near"]):
        ax.text(xi, v, f" {v:.2f}", ha="center", va="bottom", fontsize=9.5)
    ax.set_ylabel("share of lap within 2.5 s of a car ahead")
    ax.set_xlabel("track position")
    ax.set_title("Measured traffic rises down the order — the measurement never saw position")
    return _save(fig, path)


def fig_curves(fit: Fit, path: str, *, title: str | None = None) -> str:
    """Deconfounded degradation curves, plotted only over the ages actually observed."""
    style()
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for c in fit.compounds:
        lo, hi = fit.support(c)
        if not np.isfinite(lo):
            continue
        a = np.linspace(lo, hi, 120)
        y = fit.curve(c, a) - fit.curve(c, np.array([lo]))[0]
        ax.plot(a, y, lw=2.4, color=COMPOUND_COLOUR.get(c, ACCENT),
                label=f"{c.title()}  (ages {lo:.0f}–{hi:.0f})")
    ax.set_xlabel("tyre age (laps)")
    ax.set_ylabel("pace lost to tyre age (s)")
    ax.set_title(title or "Degradation, plotted only over the tyre ages the fit observed")
    ax.legend()
    return _save(fig, path)
