/* ===================================================================== *
 *  Race engineer — the state block and the deterministic templates.
 *  Implements docs/RACE_ENGINEER.md sections 1, 1.3, 1.4, 1.5 and 5.5.
 *
 *  IT NARRATES NUMBERS. IT NEVER PRODUCES THEM. Every figure it utters is
 *  computed by lib/model.js and handed to it. Turn this panel off and every
 *  number elsewhere on the page is unchanged — that is the test of whether
 *  the boundary is in the right place.
 *
 *  No API key, no network, no latency. The cached rung reads a static file;
 *  the template rung is pure arithmetic already done. Both render into the
 *  same slot with the same typography, so a judge cannot tell which rung
 *  they are looking at, and it does not matter if they can.
 * ===================================================================== */

import { round, pl } from "./model.js";

export const SCHEMA = "pitwall.race_engineer.state/1";

/* Rung 3 of the lookup ladder, verbatim from RACE_ENGINEER.md 5.4.
   The one visibly empty moment in the replay, turned into a point in our
   favour: the filtering that empties this lap is the same filtering that
   makes the model defensible. */
export const NO_DATA_CAPTION =
  "No representative green-flag laps recorded on this lap. In-laps, out-laps, " +
  "safety-car and deleted laps are filtered out before anything is measured.";

/* --------------------------------------------------------------------- *
 *  1.4 — who goes in the block.
 *  Top 5 by position, plus anyone in the pit lane this lap, plus the
 *  fastest lap of the lap. Deterministic, usually 5–7 rows, and it always
 *  includes the two cars a stop is actually about.
 * --------------------------------------------------------------------- */
function selectDrivers(rows, pittedSet) {
  const ranked = [...rows].sort(
    (a, b) => (a.position ?? 99) - (b.position ?? 99),
  );
  const keep = new Set(ranked.slice(0, 5).map((r) => r.driver));
  ranked.forEach((r) => {
    if (pittedSet.has(r.driver)) keep.add(r.driver);
  });
  const timed = ranked.filter((r) => r.lap_time_s != null);
  if (timed.length) {
    const fastest = timed.reduce((a, b) => (b.lap_time_s < a.lap_time_s ? b : a));
    keep.add(fastest.driver);
  }
  return ranked.filter((r) => keep.has(r.driver));
}

/* --------------------------------------------------------------------- *
 *  Build the block.
 *  `cleanRows` must already be filtered to this lap and to clean:true —
 *  those are the rows the model was fitted on, and the only ones whose pace
 *  means anything. `stops` must be the WHOLE race array; this function
 *  applies the pit_lap <= L filter itself so no caller can forget it.
 * --------------------------------------------------------------------- */
export function buildState({
  race,
  lap,
  cleanRows,
  stops,
  focusDriver,
  targetCompound = "HARD",
  gapAheadS = 1.5,
  M,
  headline,
}) {
  if (!cleanRows || cleanRows.length === 0) return null;

  // 1.3 leak 1 — stops[] knows the future. At Austria lap 16 the array
  // already says VER pits on lap 17. Filter before deriving anything.
  const soFar = (stops ?? []).filter((s) => s.pit_lap <= lap);
  const pittedSet = new Set(
    soFar.filter((s) => s.pit_lap === lap).map((s) => s.driver),
  );

  const drivers = selectDrivers(cleanRows, pittedSet).map((r) => {
    const pair = `${r.compound}>${targetCompound}`;
    const age = Number(r.tyre_age);
    return {
      driver: r.driver,
      position: r.position != null ? Math.round(r.position) : null,
      compound: r.compound,
      tyre_age: Number.isFinite(age) ? Math.round(age) : null,
      lap_time_s: round(r.lap_time_s, 3),
      deg_vs_fresh_s: round(M.degVsFresh(age), 2),
      deg_marginal_s: round(
        age >= M.D.peak_age ? 0 : M.D.b1 + 2 * M.D.b2 * age,
        3,
      ),
      tyre_saturated: age >= M.D.peak_age,
      stop_gain_s: M.hasPair(pair) ? round(M.step0(pair, race.track_temp_c), 2) : null,
      target_pair: M.hasPair(pair) ? pair : null,
      pitted_this_lap: pittedSet.has(r.driver),
    };
  });

  const me = drivers.find((d) => d.driver === focusDriver) ?? null;
  const rival =
    me && me.position != null
      ? drivers.find((d) => d.position === me.position - 1) ?? null
      : null;

  let undercut = null;
  if (me && rival && me.target_pair) {
    const u = M.undercut({
      pair: me.target_pair,
      trackTemp: race.track_temp_c,
      mine: me.tyre_age,
      theirs: rival.tyre_age,
      gap: gapAheadS,
      laps: 3, // 1.4 — k = 1..3 only. The interesting answer is always 1 or 2.
    });
    undercut = {
      me: me.driver,
      rival: rival.driver,
      // 1.2 — there is no gap field in artifacts/demo and none can be derived.
      // This is the operator's assumption and it is labelled as one.
      gap_ahead_s: round(gapAheadS, 1),
      gap_source: "ui_input",
      pair: me.target_pair,
      my_tyre_age: me.tyre_age,
      rival_tyre_age: rival.tyre_age,
      step0_s_per_lap: round(u.step0, 2),
      first_lap_gain_s: round(u.firstLapGain, 2),
      works: u.clears,
      needs_them_out_laps: u.needsThemOut,
      tyre_deficit_laps: u.tyreDeficit,
      rows: u.rows.map((r) => ({
        they_respond_after_laps: r.k,
        time_gained_s: round(r.gained, 2),
        gap_after_s: round(r.after, 2),
        ahead: r.ahead,
      })),
      extrapolating: u.extrapolating,
    };
  }

  const flags = [];
  if (drivers.some((d) => d.pitted_this_lap)) flags.push("PIT_STOPS_THIS_LAP");
  if (me?.pitted_this_lap) flags.push("FOCUS_PITTED_THIS_LAP");
  if (rival?.pitted_this_lap) flags.push("RIVAL_PITTED_THIS_LAP");
  if (me?.tyre_saturated) flags.push("TYRE_PAST_SATURATION");
  if (undercut?.extrapolating) flags.push("EXTRAPOLATING");
  if (undercut && undercut.works === false) flags.push("UNDERCUT_NOT_AVAILABLE");

  return {
    schema: SCHEMA,
    round: race.round,
    event: race.event,
    lap,
    race_laps: race.laps,
    track_temp_c: round(race.track_temp_c, 1),
    // 1.3 leak 2 — this is a race mean, constant for every lap of the replay.
    // The track never heats up or cools down during this demo.
    track_temp_basis: "race mean; constant for every lap of this replay",
    pit_loss_s: round(race.pit_loss_s, 2),
    focus_driver: focusDriver,
    target_compound: targetCompound,
    deg_reference_age: M.raw.fresh_age,
    drivers,
    ...(undercut ? { undercut } : {}),
    flags,
    provenance: {
      stops_analysed: headline.stops,
      events: headline.events,
      oos_rmse_s: round(headline.rmse_s, 2),
      calib_slope: round(headline.calib_slope, 2),
    },
  };
}

/* --------------------------------------------------------------------- *
 *  5.5 — the deterministic templates.
 *  These are the floor. Always correct, always instant, and they say the
 *  same numbers in the same layout the model would.
 * --------------------------------------------------------------------- */

export function replayLine(d) {
  if (!d) return null;
  const parts = [
    `P${d.position} ${d.driver}, ${String(d.compound).toLowerCase()} ${pl(d.tyre_age, "lap")} old,`,
    `${d.deg_vs_fresh_s} s/lap down on a fresh set.`,
  ];
  // Guard the missing pair: INTERMEDIATE and null compounds have no entry in
  // model.pairs, and pricing them as HARD>HARD would be a wrong number on air.
  if (d.stop_gain_s != null) parts.push(`A stop now is worth ${d.stop_gain_s} s/lap.`);
  return parts.join(" ");
}

export function undercutLine(u) {
  if (!u) return null;
  const gain = u.first_lap_gain_s;
  const signedGain = gain < 0 ? `−${Math.abs(gain).toFixed(2)}` : `+${gain.toFixed(2)}`;
  if (u.works) {
    // The cost is stated in the same sentence as the gain, for the same reason
    // the system prompt requires it of the model.
    return (
      `Undercut on ${u.rival}: ${signedGain} s on the first lap out from ` +
      `${u.gap_ahead_s} s behind. They have to stay out ` +
      `${pl(u.needs_them_out_laps, "lap")}. You rejoin ` +
      `${pl(u.tyre_deficit_laps, "lap")} older than them.`
    );
  }
  return (
    `No undercut on ${u.rival} from ${u.gap_ahead_s} s: the stop is worth ` +
    `${gain.toFixed(2)} s on the first lap out, and that does not clear them.`
  );
}

/* Pick the single thing that matters this lap, the way the prompt tells the
   model to. Do not read the block back. */
export function narrate(state) {
  if (!state) return { text: NO_DATA_CAPTION, source: "no_data" };

  const focus = state.drivers.find((d) => d.driver === state.focus_driver);

  if (state.flags.includes("FOCUS_PITTED_THIS_LAP")) {
    return {
      text: `${state.focus_driver} is in the pit lane this lap. ${replayLine(focus) ?? ""}`.trim(),
      source: "template",
    };
  }
  if (state.undercut) {
    return { text: undercutLine(state.undercut), source: "template" };
  }
  const line = replayLine(focus);
  if (line) return { text: line, source: "template" };
  return { text: NO_DATA_CAPTION, source: "no_data" };
}
