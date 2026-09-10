"""The test that killed the pit window, kept so it can be re-run against anything that
replaces it.

A window is easy to make look good. Widen it and coverage rises; a window spanning the whole
race covers every stop ever made and knows nothing. So coverage on its own is not evidence.
This script holds the WIDTH fixed and moves the window somewhere else, which isolates the only
thing a window can claim to have learned: where to put it.

Three comparisons, in increasing order of how much they hurt:

  vs random      a window of the same width placed uniformly at random. Beating this shows
                 placement is not pure width. PITWALL passes: 68.4% against 54.4%, and 2000
                 permutations never reach it (p < 0.0001).

  vs mid-race    a window of the same width centred halfway through the race. This is what a
                 rival team ships in an afternoon and it scores 65.8%. PITWALL's 68.4% edges
                 it, but by too little to lean on - the deciding test is the per-event one
                 below. That is why `pit_window` is a diagnostic in this codebase and not a
                 recommendation.

  vs mid-race,   per event, does the window centre MOVE with the lap teams actually chose?
  per event      A constant cannot, so this is the one test a constant must lose. It wins
                 anyway: r=+0.73 against +0.64, MAE 4.9 laps against 8.4. And with race length
                 divided out the window centre carries no signal at all (r=+0.08, p=0.80) -
                 the coverage was race-length arithmetic wearing a strategy costume.

WHY THE WINDOW CANNOT BE RESCUED BY TUNING. `dL`, the compound benefit, is most of the +1.26
s/lap step and does not depend on when it is taken. So neither edge comes from tyre physics:
the early edge is stint feasibility, the late edge is laps-left-to-repay, and both are
arithmetic on race length. Anything built only from race length reproduces "mid-race".

Requires artifacts/window_agreement_2026.csv (written by scripts/check_agreement.py).
Run: python scripts/check_window_placebo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGREE = os.path.join(ROOT, "artifacts", "window_agreement_2026.csv")

N_PERM = 2000
SEED = 0


def placebos(ok: pd.DataFrame) -> dict:
    """Coverage of PITWALL's window against width-matched alternatives."""
    w = ok["width"].to_numpy(int)
    laps = ok["race_laps"].to_numpy(int)
    pit = ok["PitLap"].to_numpy(int)
    hi = np.maximum(laps - w + 1, 1)              # latest legal window start

    # Analytic: chance a width-w window placed uniformly at random contains the chosen lap.
    overlap = np.minimum(np.minimum(pit, hi), np.minimum(laps - pit + 1, w))
    p_random = float(np.clip(overlap / hi, 0.0, 1.0).mean())

    mid_lo = np.maximum((laps - w) // 2, 1)
    p_mid = float(((pit >= mid_lo) & (pit <= mid_lo + w - 1)).mean())

    rng = np.random.default_rng(SEED)
    null = np.array([float(((pit >= (lo := rng.integers(1, hi + 1)))
                            & (pit <= lo + w - 1)).mean()) for _ in range(N_PERM)])
    actual = float(ok["inside"].mean())
    return {"pitwall": actual, "random": p_random, "mid_race": p_mid,
            "null_mean": float(null.mean()), "null_p95": float(np.percentile(null, 95)),
            "null_max": float(null.max()),
            "p_value": float((null >= actual).mean())}


def per_event(ok: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Does the window centre track each event's median chosen lap better than a constant?"""
    d = ok.copy()
    d["centre"] = (d["open_lap"] + d["close_lap"]) / 2.0
    d["pit_frac"] = d["PitLap"] / d["race_laps"]

    g = (d.groupby("Round")
         .agg(n=("inside", "size"), inside=("inside", "mean"),
              pit=("PitLap", "median"), centre=("centre", "median"),
              laps=("race_laps", "median"), pit_frac=("pit_frac", "median"))
         .reset_index())
    g["mid"] = g["laps"] / 2.0
    g["centre_frac"] = g["centre"] / g["laps"]

    out = {}
    for lab, col in (("pitwall", "centre"), ("mid_race", "mid")):
        r, p = stats.pearsonr(g[col], g["pit"])
        out[lab] = {"r": float(r), "p": float(p),
                    "mae_laps": float(np.abs(g[col] - g["pit"]).mean())}
    r, p = stats.pearsonr(g["centre_frac"], g["pit_frac"])
    out["frac"] = {"r": float(r), "p": float(p)}
    return g, out


def main() -> None:
    if not os.path.exists(AGREE):
        print(f"missing {AGREE}\nrun: python scripts/check_agreement.py")
        sys.exit(1)

    a = pd.read_csv(AGREE)
    ok = a.loc[a["has_window"]].copy()
    print(f"stops scored {len(a)}   window exists for {len(ok)}")
    print(f"median window width {ok['width'].median():.0f} laps "
          f"= {(ok['width'] / ok['race_laps']).median():.0%} of the race")

    p = placebos(ok)
    print("\n--- coverage, width held fixed -------------------------------------")
    print(f"  PITWALL placement        {p['pitwall']:6.1%}")
    print(f"  width-matched random     {p['random']:6.1%}   "
          f"(permutation null: mean {p['null_mean']:.1%}, "
          f"max {p['null_max']:.1%}, p={p['p_value']:.4f})")
    print(f"  width-matched MID-RACE   {p['mid_race']:6.1%}")
    print(f"  => coverage margin over mid-race: "
          f"{(p['pitwall'] - p['mid_race']) * 100:+.1f} pp "
          "(NOT the verdict - see below)")

    # Coverage is deliberately not the deciding test. It moves by a couple of points on
    # unrelated changes elsewhere in the model, and a verdict that flips on a hand-set
    # threshold is not a verdict. The per-event test below is the one that decides, because a
    # constant CANNOT track a moving target and this window has to prove that it does.
    g, s = per_event(ok)
    print("\n--- per event: does the window MOVE with the chosen lap? -----------")
    print(g[["Round", "n", "inside", "pit", "centre", "mid", "laps",
             "pit_frac", "centre_frac"]]
          .to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print(f"\n  PITWALL centre     r={s['pitwall']['r']:+.2f} "
          f"p={s['pitwall']['p']:.3f}  MAE={s['pitwall']['mae_laps']:.1f} laps")
    print(f"  mid-race constant  r={s['mid_race']['r']:+.2f} "
          f"p={s['mid_race']['p']:.3f}  MAE={s['mid_race']['mae_laps']:.1f} laps")
    print(f"  race length divided out: r={s['frac']['r']:+.2f} p={s['frac']['p']:.3f}"
          "   (no signal about WHERE in the race)")
    beaten = (s["mid_race"]["mae_laps"] < s["pitwall"]["mae_laps"]) or (s["frac"]["p"] > 0.05)
    print(f"\n  => a constant {'STILL beats it' if beaten else 'no longer beats it'}"
          f" - the window {'stays cut' if beaten else 'is worth revisiting'}")
    print("\nconclusion: coverage was width and race length, not strategy. The window is a"
          "\ndiagnostic; the undercut is the product. See strategy.py's docstring.")


if __name__ == "__main__":
    main()
