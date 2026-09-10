"""Does the undercut call actually predict who comes out ahead? Tested against real duels.

Everything else in this repo validates the model against a MEASURED QUANTITY - the step in
lap time across a pit stop, 0.96 s/lap RMSE out of sample. That is a good number and it is
honestly earned, but it is one level removed from the thing an engineer cares about, which is
whether they gain a place. This script closes that gap by scoring the undercut against the
only outcome that matters and that we did not model: track position.

THE UNIT OF OBSERVATION IS A DUEL, NOT A STOP. Absolute finishing position is useless here,
because position around any pit stop is dominated by the pit cycle: you drop four places on
the in-lap and take them back over the next fifteen as everyone else stops. That churn has
nothing to do with tyres and it swamps the effect. So the test is head-to-head instead:

    A is running directly behind B. A stops on lap L. B stops later, on lap L + k.
    Once both cars have completed their stops, is A ahead of B?

That is exactly the undercut, and it is the situation the function was written for - two cars
in close company, one blinks first. It also disposes of the pit-cycle confound by construction,
because both cars pay the same pit loss within a few laps of each other.

WHAT THE MODEL IS AND IS NOT TOLD. It gets A's compound pair, A's tyre age, B's tyre age, the
gap, and the track temperature as of lap L - all observable on the pit wall before the call.
It is trained leave-one-event-out, so the model scoring a duel at Silverstone has never seen
Silverstone. It is also told k, how long B stayed out, which was NOT knowable at lap L. That is
deliberate and it is not an outcome leak: how long the rival stays out is the rival's decision,
not a consequence of who wins, and the counterfactual "would the undercut have worked" is only
defined once you fix it. The claim under test is therefore conditional - given the rival
responded after k laps, did we call the winner - which is also the form the question takes on
the pit wall, where you are deciding against an assumed response.

`d_close` IS FORCED TO ZERO. The stop table's traffic term is `close_old - close_new`, and
`close_new` is measured on the stint AFTER the stop. Feeding it to a pre-stop prediction would
be a small causality leak of exactly the kind `_causal_track_temp` was written to remove. Zero
is the honest neutral assumption: traffic unchanged. (Note for whoever touches `S_scenario`
next - it still passes the row's own `d_close`, which is fine for the window diagnostic it
feeds and would not be fine in a live path.)

THE PLACEBOS, WHICH ARE THE POINT. A flag that fires on every duel "predicts" every win. The
pit window died in this repo because it beat random and lost to `pit halfway through the race`
(see `check_window_placebo.py`), and the same discipline applies here. Three competitors:

    base rate      call every undercut a winner. Any flag must beat this or it knows nothing.
    gap only       rank duels by how close A was. This is what you get from a stopwatch and no
                   model at all, and it is the one that would hurt.
    response only  rank by how long B stayed out. Free information, no tyre physics.

Ranking power is reported as AUC so that nothing depends on a tuned threshold - a threshold is
the same trick as a widened window. The 2x2 at the model's own natural cut-off is reported too,
because that is the form the claim takes on a slide.

THE RESULT: THE MODEL DOES NOT BEAT THE STOPWATCH, AND THE ARITHMETIC SAYS IT CANNOT.

    P(A wins | we called it)     34.2%        137 duels, 10 events, leave-one-event-out
    P(A wins | we called against) 5.2%        Fisher OR 9.5, p < 0.0001

That 2x2 is real and it is the temptation. Then the placebos:

    PITWALL margin (uses k)      AUC 0.728
    PITWALL margin (k = 1)       AUC 0.836
    gap only                     AUC 0.836    <- identical, and free
    the model's term ALONE       AUC 0.490    <- a coin flip

Paired bootstrap on margin(k=1) minus gap-only: +0.001, 95% CI [-0.026, +0.027]. Not a near
miss, not underpowered - the two rules order the duels the same way. And the reason is a ruler,
not a modelling failure. The margin is `gain - gap`. Across these duels the gain the model
supplies has sd 0.46 s; the gap has sd 14.6 s and spans 0.1 to 155 s. A term thirty times
smaller than the one it is subtracted from cannot change the ordering, so `gain - gap` is
`-gap` wearing a model. Restricting to duels close enough for that not to be true (gap < 2 s,
n=37) does not rescue it: AUC 0.374, worse than chance.

Using the real k makes it WORSE, which is the one genuinely interesting sub-finding. `k` is
supposed to be the rival's response, and for small k it is. At k >= 9 it is not a response at
all - it is the rival's own unrelated schedule - and there the model calls the undercut on 88%
of duels and gets 38% of them right. Advantage that accumulates over laps the rival was never
reacting to is advantage the model invents.

WHAT THIS DOES AND DOES NOT KILL. It does not touch the step model: that predicts seconds per
lap, it is scored against measured seconds per lap, and it still returns 0.96 s/lap RMSE out of
sample. What it kills is the promotion of that number into a claim about PLACES. Position is
decided by the gap, by traffic, by the rival's response and by who was quicker anyway - the
logit below puts `gap_s` at p=0.006 and `pace_delta_s` at p=0.002 while the model's own margin
lands at p=0.17. So the product may say what a fresh tyre is worth per lap, and may do the
subtraction on screen, and may NOT say that it predicts the overtake better than the pit wall's
own clock. It does not.

Kept, like `check_window_placebo.py`, because the metric that killed a claim is worth more than
the one that flattered it, and because anything that later claims to predict position has to
beat AUC 0.836 from a stopwatch first.

Run: python scripts/check_undercut_backtest.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall import strategy as S                                  # noqa: E402
from pitwall.stopvalue import MIN_TRAIN_EVENTS, stop_table         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "artifacts", "undercut_backtest_2026.csv")

SETTLE_LAPS = 2      # laps after the LATER stop before the outcome is read: the out-lap and
                     # the lap behind it are still cold-tyre noise, not the settled order.
SETTLE_MAX = 8       # how far forward to keep looking for a lap both cars are on track for
PACE_LAPS = 3        # laps before the stop used to measure who was quicker anyway
MAX_K = 40           # a rival who stays out 40 laps longer is not responding to anything
N_BOOT = 2000
SEED = 0


# --------------------------------------------------------------------------- duels

def duels(season: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
    """Every head-to-head undercut attempt in the season, with its observed outcome.

    An attempt is a stop by A on lap L where some car B was directly ahead of A on lap L-1 and
    B did not stop until later. `won` is whether A was ahead of B once both had settled.
    """
    race = season.loc[season["IsRace"]].copy()
    race["LapNumber"] = race["LapNumber"].astype(int)
    race["Position"] = race["Position"].astype(int)

    idx = ["Round", "Driver", "LapNumber"]
    pos = race.set_index(idx)["Position"]
    start = race.set_index(idx)["LapStartS"]
    ltime = race.set_index(idx)["LapTimeS"]
    tage = race.set_index(idx)["TyreAge"]
    comp = race.set_index(idx)["Compound"]

    # laps present per (round, lap), sorted by position - the running order on that lap
    order = {rl: g.sort_values("Position")[["Driver", "Position"]].to_numpy()
             for rl, g in race.groupby(["Round", "LapNumber"])}
    later = {(int(r), d): np.sort(g["PitLap"].astype(int).to_numpy())
             for (r, d), g in stops.groupby(["Round", "Driver"])}

    def mean_pace(rnd, drv, last_lap):
        v = [ltime.get((rnd, drv, lap)) for lap in range(last_lap - PACE_LAPS + 1, last_lap + 1)]
        v = [x for x in v if x is not None and np.isfinite(x)]
        return float(np.mean(v)) if len(v) >= 2 else np.nan

    rows = []
    for _, s in stops.iterrows():
        rnd, a, lap = int(s["Round"]), str(s["Driver"]), int(s["PitLap"])
        prev = lap - 1
        grid = order.get((rnd, prev))
        if grid is None:
            continue
        me = [i for i, (d, _) in enumerate(grid) if d == a]
        if not me or me[0] == 0:                      # not on track, or leading - no one to pass
            continue
        b = str(grid[me[0] - 1][0])                   # the car directly ahead

        b_stops = later.get((rnd, b))
        after = b_stops[b_stops > lap] if b_stops is not None else np.array([])
        if after.size == 0:
            continue                                  # B never responded: not an undercut duel
        b_lap = int(after[0])
        k = b_lap - lap
        if k < 1 or k > MAX_K:
            continue

        ta = start.get((rnd, a, prev))
        tb = start.get((rnd, b, prev))
        if ta is None or tb is None or not np.isfinite(ta) or not np.isfinite(tb):
            continue
        gap = float(ta) - float(tb)                   # positive: A is behind B
        if gap <= 0:                                  # position and clock disagree (lapped car)
            continue

        settled = max(lap, b_lap)
        out_lap = None
        for cand in range(settled + SETTLE_LAPS, settled + SETTLE_MAX + 1):
            if (rnd, a, cand) in pos.index and (rnd, b, cand) in pos.index:
                out_lap = cand
                break
        if out_lap is None:
            continue

        age_b = tage.get((rnd, b, prev))
        rows.append({
            "Round": rnd, "attacker": a, "rival": b,
            "PitLap": lap, "rival_pit_lap": b_lap, "k": k,
            "gap_s": gap,
            "pair": str(s["pair"]), "age_old": float(s["age_old"]), "tt": float(s["tt"]),
            "rival_age": float(age_b) if age_b is not None else np.nan,
            "rival_compound": str(comp.get((rnd, b, prev))),
            "same_compound": str(comp.get((rnd, b, prev))) == str(s["c_old"]),
            "pos_before": int(pos.loc[(rnd, a, prev)]),
            "rival_pos_before": int(pos.loc[(rnd, b, prev)]),
            "out_lap": out_lap,
            "pos_after": int(pos.loc[(rnd, a, out_lap)]),
            "rival_pos_after": int(pos.loc[(rnd, b, out_lap)]),
            "won": bool(pos.loc[(rnd, a, out_lap)] < pos.loc[(rnd, b, out_lap)]),
            "pace_delta_s": mean_pace(rnd, a, prev) - mean_pace(rnd, b, prev),
        })
    d = pd.DataFrame(rows)
    return d.dropna(subset=["rival_age"]).reset_index(drop=True)


# --------------------------------------------------------------------------- the call

def verdicts(d: pd.DataFrame, stops: pd.DataFrame, *, loo: bool = True) -> pd.DataFrame:
    """Attach the undercut call the engine would have made before each duel."""
    out = []
    for rnd, held in d.groupby("Round"):
        train = stops.loc[stops["Round"] != rnd] if loo else stops
        if train["Round"].nunique() < MIN_TRAIN_EVENTS:
            continue
        deg = S.fit_degradation(train)
        model = S.fit_level_model(train)

        grid = pd.DataFrame({"pair": held["pair"].to_numpy(),
                             "age_old": held["age_old"].to_numpy(float),
                             "tt": held["tt"].to_numpy(float),
                             "d_close": 0.0})            # see module docstring
        step0 = np.asarray(model.predict(grid), float)

        h = held.copy()
        h["step0_s"] = step0
        gained, lap1, margin, need = [], [], [], []
        for (_, r), s0 in zip(h.iterrows(), step0):
            u = S.undercut(deg, step0=float(s0), age_mine=float(r["age_old"]),
                           age_theirs=float(r["rival_age"]), gap_s=float(r["gap_s"]),
                           laps=int(r["k"]))
            g = float(u["time_gained_s"].iloc[-1])       # gain by the lap they responded
            gained.append(g)
            lap1.append(float(u["time_gained_s"].iloc[0]))   # what the pit wall can know
            margin.append(g - float(r["gap_s"]))         # >0 : model says A clears B
            first = u.loc[u["ahead"]]
            need.append(int(first["they_respond_after_laps"].iloc[0]) if not first.empty else None)
        h["gain_by_k_s"] = gained
        h["gain_lap1_s"] = lap1
        h["margin_s"] = margin
        h["margin_lap1_s"] = np.asarray(lap1) - h["gap_s"].to_numpy(float)
        h["needs_them_out_for"] = need
        h["call_ahead"] = h["margin_s"] > 0.0
        h["extrapolating"] = h["age_old"] > deg.max_age_seen
        out.append(h)
    return pd.concat(out, ignore_index=True) if out else d.iloc[:0]


# --------------------------------------------------------------------------- scoring

def auc(score: np.ndarray, y: np.ndarray) -> float:
    """P(score of a win > score of a loss). 0.5 is a coin flip, and no threshold is tuned."""
    score, y = np.asarray(score, float), np.asarray(y, bool)
    if y.all() or (~y).all():
        return float("nan")
    u = stats.mannwhitneyu(score[y], score[~y], alternative="two-sided").statistic
    return float(u / (y.sum() * (~y).sum()))


def boot_auc_gap(a: np.ndarray, b: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Paired bootstrap on AUC(a) - AUC(b): same resampled duels scored by both rules."""
    rng = np.random.default_rng(SEED)
    n = len(y)
    diffs = []
    for _ in range(N_BOOT):
        i = rng.integers(0, n, n)
        if y[i].all() or (~y[i]).all():
            continue
        diffs.append(auc(a[i], y[i]) - auc(b[i], y[i]))
    diffs = np.asarray(diffs)
    return (float(np.mean(diffs)), float(np.percentile(diffs, 2.5)),
            float(np.percentile(diffs, 97.5)))


def two_by_two(flag: np.ndarray, y: np.ndarray) -> dict:
    flag, y = np.asarray(flag, bool), np.asarray(y, bool)
    tp, fp = int((flag & y).sum()), int((flag & ~y).sum())
    fn, tn = int((~flag & y).sum()), int((~flag & ~y).sum())
    p_flag = tp / (tp + fp) if tp + fp else float("nan")
    p_not = fn / (fn + tn) if fn + tn else float("nan")
    odds = stats.fisher_exact([[tp, fp], [fn, tn]])
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "p_when_flagged": p_flag, "p_when_not": p_not,
            "lift": p_flag - p_not, "base": float(y.mean()),
            "accuracy": float(((flag == y).mean())),
            "odds_ratio": float(odds[0]), "p_value": float(odds[1])}


def main() -> None:
    season = pd.read_parquet(os.path.join(ROOT, "data", "season_2026.parquet"))
    stops = stop_table(season)

    d = duels(season, stops)
    print(f"stops in season      : {len(stops)}")
    print(f"head-to-head duels   : {len(d)}   "
          f"({d['Round'].nunique()} events, {d['won'].mean():.1%} won by the attacker)")

    v = verdicts(d, stops, loo=True)
    if v.empty:
        print("no scorable duels")
        return
    v.to_csv(OUT, index=False)
    y = v["won"].to_numpy(bool)
    print(f"scored leave-one-out : {len(v)}   base rate {y.mean():.1%}\n")

    print("--- 2x2 at the model's own cut-off (margin > 0) --------------------")
    t = two_by_two(v["call_ahead"].to_numpy(bool), y)
    print(f"  called ahead, won    {t['tp']:4d}      called ahead, lost   {t['fp']:4d}")
    print(f"  called behind, won   {t['fn']:4d}      called behind, lost  {t['tn']:4d}")
    print(f"  P(win | called ahead)  = {t['p_when_flagged']:.1%}")
    print(f"  P(win | called behind) = {t['p_when_not']:.1%}")
    print(f"  lift over the other arm = {t['lift']:+.1%}   "
          f"base rate {t['base']:.1%}   accuracy {t['accuracy']:.1%}")
    print(f"  Fisher exact: OR {t['odds_ratio']:.2f}, p = {t['p_value']:.4f}")

    print("\n--- ranking power, no threshold tuned ------------------------------")
    rules = {
        "PITWALL margin (uses k)": v["margin_s"].to_numpy(float),
        "PITWALL margin (k = 1) ": v["margin_lap1_s"].to_numpy(float),
        "gap only               ": -v["gap_s"].to_numpy(float),
        "the model's term ALONE ": v["gain_lap1_s"].to_numpy(float),
        "response only          ": v["k"].to_numpy(float),
        "pace before            ": -v["pace_delta_s"].to_numpy(float),
    }
    for name, sc in rules.items():
        ok = np.isfinite(sc)
        print(f"  {name} AUC {auc(sc[ok], y[ok]):.3f}   (n={int(ok.sum())})")

    g = rules["gap only               "]
    for lab in ("PITWALL margin (uses k)", "PITWALL margin (k = 1) "):
        dm, lo, hi = boot_auc_gap(rules[lab], g, y)
        tag = "BEATEN by the stopwatch" if hi < 0 else \
              "no separation from the stopwatch" if lo < 0 < hi else "genuinely better"
        print(f"\n  {lab.strip()} - gap only : {dm:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  <- {tag}")

    print("\n--- why: a 0.5 s term subtracted from a 15 s one cannot reorder it --")
    for c in ("gain_lap1_s", "gain_by_k_s", "gap_s"):
        s = v[c]
        print(f"  {c:12s} sd {s.std():6.2f} s   range {s.min():7.2f} to {s.max():7.2f}")
    print(f"  ratio sd(gap) / sd(model term) = {v['gap_s'].std() / v['gain_lap1_s'].std():.1f}x")

    print("\n--- does it survive controls? logit(won) ---------------------------")
    try:
        import statsmodels.api as sm
        X = pd.DataFrame({
            "margin_s": v["margin_s"], "gap_s": v["gap_s"], "k": v["k"].astype(float),
            "pace_delta_s": v["pace_delta_s"],
        }).astype(float)
        keep = X.notna().all(axis=1)
        res = sm.Logit(y[keep.to_numpy()], sm.add_constant(X.loc[keep])).fit(disp=0)
        print(res.summary2().tables[1].to_string(float_format=lambda x: f"{x:.4f}"))
        print("  (margin_s carries the model; gap_s and pace_delta_s are the free alternatives)")
    except Exception as exc:                                       # noqa: BLE001
        print(f"  logit unavailable: {exc}")

    print("\n--- where it goes wrong --------------------------------------------")
    v["bucket"] = pd.cut(v["k"], [0, 1, 2, 4, 8, MAX_K],
                         labels=["1", "2", "3-4", "5-8", "9+"])
    print(v.groupby("bucket", observed=True)
          .agg(n=("won", "size"), won=("won", "mean"), called=("call_ahead", "mean"),
               acc=("call_ahead", lambda c: float((c.to_numpy(bool)
                                                   == v.loc[c.index, "won"]).mean())))
          .to_string(float_format=lambda x: f"{x:.2f}"))
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
