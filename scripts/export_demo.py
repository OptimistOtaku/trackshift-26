"""Emit the static JSON the demo runs on. No server at demo time, nothing to go wrong on stage.

Writes artifacts/demo/ per docs/DEMO_CONTRACT.md: an index with the headline numbers, the
fitted coefficients so the UI can compute undercuts client-side, and one file per race for the
replay scrubber.

The coefficients are exported rather than the predictions because the hero feature is
interactive - the user moves a gap or a tyre age and the answer changes. Shipping predictions
would mean a round trip we do not have, or a pre-computed grid we would have to guess the
extent of.

The one exception is `degradation_curves`, which ships sampled curves rather than
coefficients. Nothing interactive hangs off it - it is a picture of the naive practice fit
next to the deconfounded one, and of the race phi - so handing the UI a list of points
removes any chance of the clamp at `peak_age` being dropped on the way to a canvas.

Run: python scripts/export_demo.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall import strategy as S                                  # noqa: E402
from pitwall.degradation import REF_AGE, fit_practice, fit_race    # noqa: E402
from pitwall.stopvalue import SPECS, loo_evaluate, stop_table      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
OUT = os.path.join(ART, "demo")

# Columns the replay needs. Kept explicit: dumping every column would put the fitted
# RunPaceRef and TrackEvo in the UI's hands, and those are model internals, not observations.
LAP_COLS = ["lap", "driver", "lap_time_s", "compound", "tyre_age", "position",
            "fuel_kg", "frac_close"]


def _round_floats(o, nd: int = 4):
    """Trim float noise so the JSON is readable and small. 4dp is 0.1 ms on a lap time."""
    if isinstance(o, float):
        return None if not np.isfinite(o) else round(o, nd)
    if isinstance(o, dict):
        return {k: _round_floats(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [_round_floats(v, nd) for v in o]
    if isinstance(o, (np.floating,)):
        return _round_floats(float(o), nd)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _curve_points(fit, compound: str, ages: np.ndarray, anchor: float) -> list[dict]:
    """Sample one fitted practice curve as {age, delta_s}, pinned to zero at `anchor`.

    The level of a practice curve is NOT identified and must not be shipped as if it were.
    Every run gets its own intercept, and each run is a single compound, so nothing in
    practice says whether a SOFT is intrinsically quicker than a MEDIUM - see the
    `validate.py` docstring. What is identified is the SHAPE. So both curves are pinned to
    zero at the youngest tyre age the fit actually observed, and every number after that is
    "seconds per lap slower than a tyre this age", which is a claim the data supports.

    Pinning at the same anchor for both fits is also what makes the picture honest: the two
    lines start from the same point, so the gap between them at any age is entirely the
    confounding and not a difference in where someone chose to start the axis.

    Ages are whole laps and are emitted as JSON integers. A tyre age IS an integer number of
    laps, and DEMO_BRIEF already has to warn the UI to coerce the floats in `laps_data`.
    """
    base = float(fit.curve(compound, np.array([anchor], float), clip=True)[0])
    vals = np.asarray(fit.curve(compound, ages.astype(float), clip=True), float) - base
    return [{"age": int(a), "delta_s": float(v)} for a, v in zip(ages, vals)]


def _curve_side(fit, compound: str, ages: np.ndarray, anchor: float, row) -> dict:
    """One side of the comparison - naive or deconfounded - for one compound.

    The scalars come from `Fit.summary_table` and `Fit.deg_rate` rather than being recomputed
    here, so the demo cannot drift away from the ladder the deck and README quote.
    `slope_s_per_lap` is the instantaneous rate at REF_AGE, which is the number the whole
    story turns on: negative means the fit believes the tyre is getting quicker as it wears.
    """
    return {
        "b1": float(row["lin_s_per_lap"]),
        "b2": float(row["quad_s_per_lap2"]),
        "slope_s_per_lap": float(fit.deg_rate(compound, REF_AGE)),
        "total_s_over_support": float(row["loss_support_s"]),
        "curve": _curve_points(fit, compound, ages, anchor),
    }


def degradation_curves_json(season: pd.DataFrame, deg: S.Degradation, n_stops: int) -> dict:
    """The sign flip, as data the UI can draw without doing any arithmetic.

    THIS IS THE OPENING ARGUMENT OF THE WHOLE PROJECT AND IT WAS NOT IN THE DEMO DATA.

    Fit `lap_time ~ tyre_age` on practice long runs with a run intercept - the standard thing,
    and what `fit_practice` does with all three correction flags off - and two of the three
    compounds come back with a NEGATIVE age slope. At tyre age 10 the naive fit has a HARD
    gaining 0.15 s/lap for every further lap of wear. That is not a small bias, it is a sign
    error on the headline number, and it is what a reasonable person gets on the first attempt.

    The cause is collinearity inside a run. A practice long run burns exactly one lap of fuel
    for every lap the tyre ages, so within a run fuel mass is an exact affine function of tyre
    age and no amount of practice data can separate them. The age slope simply absorbs the
    fuel effect, which has the opposite sign, and wins.

    The fix is not a better practice fit, it is a different place to look. `fit_race` estimates
    the fuel sensitivity lambda on RACE laps, where stints begin at different points in the
    race and the same tyre age is therefore observed at many different fuel loads - so fuel and
    age are not collinear and lambda is identified. Subtract `lambda * FuelKg` from practice
    lap times, add the measured rubber term, and the slope flips to the physically correct
    sign. lambda lands at +0.029 s/kg against a literature range of 0.030-0.035 s/kg, which is
    the check that this is a real quantity and not a fitting artefact.

    WHICH TWO FITS. Exactly the ends of the ablation ladder in `validate.py` and
    `artifacts/q1_ladder_2026.csv`: naive is all three correction flags off, deconfounded is
    all three on. Refitted here from the same code path rather than reimplemented, so the demo
    and the deck cannot disagree. lambda is pooled over all twelve races, because this block
    DESCRIBES the season rather than forecasting anything - the leave-one-event-out version
    lives in `validate.py` and is what the validation numbers are quoted from.

    WHAT THE UI MAY DO WITH IT: draw it. Nothing else. The deconfounded practice curve is
    defensible in sample and does not transfer to a race - calibration slope +0.006 against the
    measured pit-stop step, see README question 3 - which is the reason `stopvalue.py` exists.
    The curve the product actually computes with is `race` below, which is the same phi as the
    `degradation` block above, sampled so the two are visibly one object.
    """
    prac = season.loc[~season["IsRace"]]
    fr = fit_race(season)
    lam = float(fr.lambda_fuel)

    naive = fit_practice(prac, lambda_fuel=lam,
                         correct_fuel=False, use_traffic=False, use_evo=False)
    deconf = fit_practice(prac, lambda_fuel=lam,
                          correct_fuel=True, use_traffic=True, use_evo=True)
    nt = naive.summary_table().set_index("compound")
    dt = deconf.summary_table().set_index("compound")

    compounds = {}
    for c in deconf.compounds:
        # Both fits see the same laps, so the observed age range is the same for both and one
        # axis is enough. Taken from the deconfounded fit; asserting equality here would only
        # add a way for the export to fail on stage.
        lo, hi = deconf.support(c)
        ages = np.arange(int(np.ceil(lo)), int(np.floor(hi)) + 1)
        s_naive = float(nt.loc[c, "deg_at_10"])
        s_deconf = float(dt.loc[c, "deg_at_10"])
        compounds[c] = {
            "age_lo": float(lo),
            "age_hi": float(hi),
            "anchor_age": float(lo),
            "naive": _curve_side(naive, c, ages, lo, nt.loc[c]),
            "deconfounded": _curve_side(deconf, c, ages, lo, dt.loc[c]),
            "sign_flip": bool(s_naive < 0.0 <= s_deconf),
        }

    # phi over every age a real stop was made at, including the flat part. Sampling it rather
    # than leaving the UI to evaluate the quadratic is deliberate: the clamp at peak_age is
    # the one piece of this model that is easiest to drop by accident and worst to drop.
    race_ages = np.arange(0, int(round(deg.max_age_seen)) + 1)
    return {
        "note": ("Practice degradation fitted two ways on the same laps. naive is lap time on "
                 "tyre age with a run intercept and nothing else; deconfounded subtracts a "
                 "fuel sensitivity identified on race laps and adds measured traffic and "
                 "rubber. Within a practice run fuel burn is collinear with tyre age, so the "
                 "naive age slope absorbs the fuel effect and reports that tyres get FASTER "
                 "as they wear. Draw both on one axis - that is the sign flip."),
        "slope_ref_age": float(REF_AGE),
        "lambda_fuel_s_per_kg": lam,
        "lambda_se_s_per_kg": float(fr.notes.get("fuel_se", np.nan)),
        "lambda_events": int(fr.notes.get("n_events", 0)),
        "lambda_note": ("Identified on race laps, never on the practice laps it is then "
                        "applied to. Stints start at different points in a race, so the same "
                        "tyre age is seen at many fuel loads and fuel is separable from age. "
                        "Literature puts the fuel effect at 0.030-0.035 s/kg."),
        "practice": {
            "n_laps": int(deconf.n_obs),
            "n_runs": int(deconf.n_groups),
            "naive_spec": "no fuel correction, no traffic term, no track evolution",
            "deconfounded_spec": ("fuel corrected with lambda, traffic measured, "
                                  "rubber measured"),
            "anchor_note": ("delta_s is seconds per lap slower than a tyre of age anchor_age, "
                            "on the same compound. Practice identifies the SHAPE of a "
                            "degradation curve and not its level - each run has its own "
                            "intercept and each run is one compound - so both curves are "
                            "pinned to zero at anchor_age and only the shape is claimed."),
            "compounds": compounds,
        },
        "race": {
            "b1": deg.b1,
            "b2": deg.b2,
            "peak_age": deg.peak,
            "max_age_seen": deg.max_age_seen,
            "n_stops": int(n_stops),
            "curve": [{"age": int(a), "delta_s": float(deg.phi(float(a)))} for a in race_ages],
            "note": ("The same phi as the `degradation` block above, sampled so the gauge and "
                     "the curve are one object. Measured from race pit stops, not practice. "
                     "HELD FLAT past peak_age: the fitted quadratic has b2 < 0 and would bend "
                     "downwards past its peak, which would claim tyres get faster as they "
                     "wear - the sign error this project exists to point at. The flat tail in "
                     "this array is that clamp and is not a plotting mistake."),
        },
        "not_a_predictor": (
            "These practice curves are the diagnostic, not the product. The deconfounded "
            "curve is defensible in sample and does NOT transfer to a race: calibration "
            "slope +0.006 against the measured pit-stop step. Draw them to show the sign "
            "flip; do not compute an undercut or a stop value from them. Use `degradation` "
            "/ `race` for that."),
    }


def model_json(model, deg: S.Degradation, curves: dict) -> dict:
    """Fitted coefficients, in the form the JS in DEMO_CONTRACT.md expects."""
    p = model.res.params
    pairs = {model.pairs[0]: 0.0}                 # the dropped reference pair
    for name in p.index:
        if name.startswith("p[") and name.endswith("]"):
            pairs[name[2:-1]] = float(p[name])
    return {
        "spec": list(model.spec),
        "intercept": float(p.get("const", 0.0)),
        "tt_mean": float(model.tt_mean),
        "tt_coef": float(p.get("tt_c", 0.0)),
        "traf_coef": float(p.get("d_close", 0.0)),
        "pairs": pairs,
        "reference_pair": model.pairs[0],
        "degradation": {
            "b1": deg.b1, "b2": deg.b2,
            "peak_age": deg.peak, "max_age_seen": deg.max_age_seen,
            "note": ("phi(a) = b1*a + b2*a^2, HELD FLAT past peak_age. Never let it decline - "
                     "a declining phi claims tyres get faster as they wear, which is the sign "
                     "error this project exists to point at."),
        },
        "fresh_age": S.FRESH_AGE,
        "n_obs": int(model.n_obs),
        "degradation_curves": curves,
    }


def _race_length(rnd: int, observed_max: int) -> int:
    """How many laps the race actually ran, not how many survived the fit filter.

    `laps_data` is filtered to green, non-pit, accurate laps, so its highest lap number is the
    last lap someone set a CLEAN time on - which is not the end of the race. At Silverstone
    the last five laps were run behind a safety car, so the filter removed all of them and this
    field read 47 for a 52-lap race: the scrubber's track just ended early and nothing said so.

    `artifacts/demo/replay/R*.json` carries FastF1's `total_laps`, which is the real answer, so
    take it from there when the replay export has been run. Falling back to the observed max
    keeps this script standalone - it is the old behaviour, and it is only ever short.
    """
    path = os.path.join(OUT, "replay", f"R{rnd:02d}.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                n = int(json.load(f).get("laps", 0))
            if n >= observed_max:
                return n
        except (ValueError, OSError, json.JSONDecodeError):
            pass                                  # a broken replay file must not fail the demo
    return observed_max


def race_json(season: pd.DataFrame, stops: pd.DataFrame, model, rnd: int,
              pit_loss: float) -> dict:
    race = season.loc[season["IsRace"] & (season["Round"] == rnd)]
    d = race.rename(columns={"LapNumber": "lap", "Driver": "driver", "LapTimeS": "lap_time_s",
                             "Compound": "compound", "TyreAge": "tyre_age",
                             "Position": "position", "FuelKg": "fuel_kg"})
    d = d.reindex(columns=LAP_COLS)
    d = d.dropna(subset=["lap", "driver", "lap_time_s"]).sort_values(["lap", "driver"])
    for c in ("lap", "tyre_age", "position"):
        d[c] = pd.to_numeric(d[c], errors="coerce")

    st = stops.loc[stops["Round"] == rnd].copy()
    if not st.empty:
        st["step_pred_s"] = model.predict(st)
    sj = [{"driver": str(r["Driver"]), "pit_lap": int(r["PitLap"]), "pair": str(r["pair"]),
           "age_old": float(r["age_old"]), "step_obs_s": float(r["step_obs"]),
           "step_pred_s": float(r["step_pred_s"])} for _, r in st.iterrows()]

    ev = str(race["Event"].iloc[0])
    observed = int(d["lap"].max())
    laps = _race_length(rnd, observed)
    return {
        "round": int(rnd), "event": ev, "laps": laps,
        "last_clean_lap": observed,
        "pit_loss_s": float(pit_loss), "track_temp_c": float(race["TrackTemp"].mean()),
        "drivers": sorted(d["driver"].astype(str).unique().tolist()),
        "laps_data": d.to_dict(orient="records"),
        "stops": sj,
    }


def baseline_json(stops: pd.DataFrame, ev: dict) -> dict:
    """Score the deployed model against the season-mean baseline, per the contract.

    The baseline is `SPECS["mean only"]` scored through the SAME leave-one-event-out loop as
    the model - not a mean taken over the whole season. A pooled mean would have seen the
    event it is scoring on, which would flatter the baseline's competitor here by handing it
    an unfair opponent rather than a fair one, and either direction of unfairness is a
    number we would have to withdraw under a question.

    `events_won` is a per-event head-to-head rather than a pooled figure because pooled RMSE
    can be carried by one bad event. Winning 7 of 11 says the gain is broad; the pooled 11.1%
    alone does not.

    This used to be `rmse_s / (1 - 0.111)`, which derived the baseline from the improvement it
    was supposed to establish - so the "gain" was true by construction and would have silently
    stopped tracking the model.
    """
    bl = loo_evaluate(stops, SPECS["mean only"])
    if not (bl.get("n") and ev.get("rmse_s")):
        return {}

    # Same LOO filters on both sides, so the event sets match; inner-join anyway rather than
    # assume it, because a silent misalignment here would overstate events_won.
    m = (ev["per_event"].merge(bl["per_event"], on="round", suffixes=("_model", "_base")))
    return {
        "baseline_rmse_s": float(bl["rmse_s"]),
        "baseline_spec": "season mean, same leave-one-event-out loop",
        "improvement_pct": float((1.0 - ev["rmse_s"] / bl["rmse_s"]) * 100.0),
        "events_won": int((m["rmse_s_model"] < m["rmse_s_base"]).sum()),
        "events_compared": int(len(m)),
    }


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    season = pd.read_parquet(os.path.join(ROOT, "data", "season_2026.parquet"))
    stops = stop_table(season)
    loss = pd.read_csv(os.path.join(ART, "pitloss_2026.csv"))
    pit_loss = dict(zip(loss["Round"].astype(int), loss["median"].astype(float)))

    deg = S.fit_degradation(stops)
    model = S.fit_level_model(stops)
    ev = loo_evaluate(stops, S.LEVEL_SPEC)
    curves = degradation_curves_json(season, deg, len(stops))

    with open(os.path.join(OUT, "model.json"), "w", encoding="utf-8") as f:
        json.dump(_round_floats(model_json(model, deg, curves), 6), f, indent=2)

    cp = curves["practice"]["compounds"]
    print(f"degradation_curves: lambda = {curves['lambda_fuel_s_per_kg']:+.4f} s/kg")
    for c, blk in cp.items():
        print(f"  {c:7s} naive {blk['naive']['slope_s_per_lap']:+.4f} -> deconfounded "
              f"{blk['deconfounded']['slope_s_per_lap']:+.4f} s/lap at age "
              f"{curves['slope_ref_age']:.0f}"
              f"{'   SIGN FLIP' if blk['sign_flip'] else ''}")

    races, race_meta = [], []
    for rnd in sorted(stops["Round"].unique()):
        rnd = int(rnd)
        if rnd not in pit_loss:
            print(f"[R{rnd:02d}] skipped: no measured pit loss")
            continue
        rj = race_json(season, stops, model, rnd, pit_loss[rnd])
        name = f"R{rnd:02d}.json"
        os.makedirs(os.path.join(OUT, "races"), exist_ok=True)
        with open(os.path.join(OUT, "races", name), "w", encoding="utf-8") as f:
            json.dump(_round_floats(rj), f, separators=(",", ":"))
        races.append(rj)
        race_meta.append({"round": rnd, "event": rj["event"], "laps": rj["laps"],
                          "file": f"races/{name}", "pit_loss_s": rj["pit_loss_s"],
                          "track_temp_c": rj["track_temp_c"], "stops": len(rj["stops"])})
        print(f"[R{rnd:02d}] {rj['event'][:26]:26s} laps={rj['laps']:3d} "
              f"rows={len(rj['laps_data']):5d} stops={len(rj['stops']):3d}"
              f"{'   (last clean lap %d)' % rj['last_clean_lap']
                 if rj['last_clean_lap'] < rj['laps'] else ''}")

    base = baseline_json(stops, ev)
    index = {
        "season": int(season["Year"].iloc[0]),
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "headline": {
            "stops": int(len(stops)), "events": int(stops["Round"].nunique()),
            "rmse_s": float(ev["rmse_s"]), "calib_slope": float(ev["calib_slope"]),
            "mae_s": float(ev["mae_s"]), "bias_s": float(ev["bias_s"]),
            "n_scored": int(ev["n"]), "events_scored": int(ev["events"]),
            **base,
        },
        "pit_loss": {
            "season_median_s": float(loss["season_median"].iloc[0]),
            "min_s": float(loss["median"].min()), "max_s": float(loss["median"].max()),
        },
        "window_is_not_reported": (
            "A pit-lap recommendation is deliberately absent. It covers 68.4% of real stops "
            "against 65.8% for a width-matched mid-race window, a margin too small to lean on; "
            "and per event that mid-race constant tracks the chosen lap better than the window "
            "centre does. So it adds nothing over 'pit halfway through'. See "
            "scripts/check_window_placebo.py."),
        "races": race_meta,
    }
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(_round_floats(index, 6), f, indent=2)

    total = sum(os.path.getsize(os.path.join(dp, fn))
                for dp, _, fns in os.walk(OUT) for fn in fns)
    print(f"\nwrote {len(race_meta)} races to {os.path.relpath(OUT, ROOT)}  "
          f"({total / 1e6:.1f} MB total)")
    print(f"headline: RMSE {ev['rmse_s']:.3f} s/lap, calib {ev['calib_slope']:.2f}, "
          f"{len(stops)} stops")
    if base:
        print(f"          vs season mean {base['baseline_rmse_s']:.3f} s/lap = "
              f"{base['improvement_pct']:+.1f}%, winning "
              f"{base['events_won']}/{base['events_compared']} events")


if __name__ == "__main__":
    main()
