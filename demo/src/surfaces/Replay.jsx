/* ===================================================================== *
 *  3 — Race replay.
 *
 *  Reads replay/R*.json, the unfiltered feed, and every trap in
 *  REPLAY_DATA.md is handled here rather than worked around:
 *
 *    1. track_status is a CONCATENATION of the codes seen during the lap.
 *       "412" means green, then safety car, then yellow. Tested with includes,
 *       never equality.
 *    2. `clean` is read as given. It is the flag the model was fitted against;
 *       re-deriving it from the booleans would put this page and the model on
 *       different samples.
 *    3. A null lap_time_s is real data, not a hole to patch. The row stays and
 *       the gap is drawn.
 *    4. stops[] covers the whole race, so it knows the future. Filtered to
 *       pit_lap <= current lap before anything is shown.
 *    5. The lap count comes from this file. races/R09.json stops at lap 47
 *       because that is its last clean lap; the race ran 52.
 * ===================================================================== */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCommentary, getRace, getReplay } from "../lib/data.js";
import { buildState, narrate } from "../lib/engineer.js";
import { Limitation, Pill, Select, SurfaceHead, Source } from "../components/ui.jsx";
import { fmt, pl, signed } from "../lib/model.js";
import engineerPortrait from "../assets/race-engineer.png";

/* Why a row was excluded, read off the flags that travel with it. This labels
   `clean`, it does not decide it. */
function excuse(r) {
  if (r.in_lap) return "in-lap";
  if (r.out_lap) return "out-lap";
  if (r.deleted) return "deleted";
  if (!r.green) return "not green";
  if (r.lap_time_s == null) return "no time";
  return "excluded";
}

/* Rung 1 of the lookup ladder: a pre-generated line for this exact lap and
   driver. artifacts/demo/commentary/ does not exist yet, so this returns null
   and the template rung answers instead — which is the point of having a
   ladder. The shape is read tolerantly so whichever layout gen_commentary.py
   settles on, this finds it or gives up quietly. */
function cachedLine(cache, lap, driver) {
  if (!cache) return null;
  const byLap = cache.lines ?? cache.laps ?? null;
  if (byLap && !Array.isArray(byLap)) {
    const slot = byLap[String(lap)];
    if (typeof slot === "string") return slot;
    if (slot && typeof slot === "object") {
      const hit = slot[driver] ?? slot.text ?? null;
      if (typeof hit === "string") return hit;
    }
  }
  const list = Array.isArray(cache) ? cache : Array.isArray(byLap) ? byLap : cache.entries;
  if (Array.isArray(list)) {
    const hit = list.find(
      (e) => Number(e.lap) === lap && (!e.driver || e.driver === driver),
    );
    if (hit && typeof hit.text === "string") return hit.text;
  }
  return null;
}

export default function Replay({ M, index }) {
  const [round, setRound] = useState(8);
  const [replay, setReplay] = useState(null);
  const [race, setRace] = useState(null);
  const [cache, setCache] = useState(null);
  const [lap, setLap] = useState(16);
  const [focus, setFocus] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [err, setErr] = useState(null);
  const [voiceMode, setVoiceMode] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speechRef = useRef(null);

  useEffect(() => {
    let live = true;
    setReplay(null);
    setRace(null);
    setCache(null);
    setErr(null);
    getCommentary(round).then((c) => live && setCache(c));
    Promise.all([getReplay(round), getRace(round)])
      .then(([rp, rc]) => {
        if (!live) return;
        setReplay(rp);
        setRace(rc);
        setLap((l) => Math.min(Math.max(1, l), rp.laps));
      })
      .catch((e) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [round]);

  const timer = useRef(null);
  useEffect(() => {
    if (!playing || !replay) return undefined;
    timer.current = window.setInterval(() => {
      setLap((l) => Math.min(l + 1, replay.laps));
    }, 650);
    return () => window.clearInterval(timer.current);
  }, [playing, replay]);

  /* Stop at the chequered flag. Kept out of the interval's updater because a
     state setter called from inside another setter is not a pure update. */
  useEffect(() => {
    if (playing && replay && lap >= replay.laps) setPlaying(false);
  }, [playing, replay, lap]);

  const rows = useMemo(
    () => (replay ? replay.laps_data.filter((r) => r.lap === lap) : []),
    [replay, lap],
  );
  const clean = useMemo(() => rows.filter((r) => r.clean), [rows]);

  /* Trap 4. Everything below derives from stopsSoFar, never from race.stops. */
  const stopsSoFar = useMemo(
    () => (race ? race.stops.filter((s) => s.pit_lap <= lap) : []),
    [race, lap],
  );
  const pittedThisLap = useMemo(
    () => stopsSoFar.filter((s) => s.pit_lap === lap),
    [stopsSoFar, lap],
  );

  /* Trap 1. track_status is a CONCATENATION of every code seen during the lap:
     "412" is green, then safety car, then yellow. So it is read with a contains
     test, never an equality test — `status === "1"` would call that lap green
     and quietly feed a safety-car lap into a pace comparison. */
  const statuses = useMemo(() => {
    const seen = new Set();
    rows.forEach((r) => String(r.track_status ?? "").split("").forEach((ch) => seen.add(ch)));
    return [...seen].sort();
  }, [rows]);

  const interrupted = useMemo(
    () =>
      rows.some((r) => {
        const s = String(r.track_status ?? "");
        return s.includes("4") || s.includes("5") || s.includes("6") || s.includes("7");
      }),
    [rows],
  );

  /* RACE_ENGINEER focus policy: the car running second, with the leader as the
     rival. That is the fight a stop is actually about. */
  const defaultFocus = useMemo(() => {
    const second = clean.find((r) => Math.round(r.position) === 2);
    return second?.driver ?? clean[0]?.driver ?? null;
  }, [clean]);
  const focusDriver = focus && clean.some((r) => r.driver === focus) ? focus : defaultFocus;

  const state = useMemo(() => {
    if (!replay || !race || !focusDriver) return null;
    return buildState({
      race: { ...race, laps: replay.laps },
      lap,
      cleanRows: clean,
      stops: race.stops,
      focusDriver,
      targetCompound: "HARD",
      gapAheadS: 1.5,
      M,
      headline: index.headline,
    });
  }, [replay, race, clean, focusDriver, lap, M, index.headline]);

  /* The ladder: a cached line if one was generated for this lap, otherwise the
     deterministic template, otherwise the fixed no-data caption. Same slot,
     same typography, same numbers — which rung answered is not something the
     room needs to be able to tell. */
  const cached = cachedLine(cache, lap, focusDriver);
  const radio = cached ? { text: cached, source: "cache" } : narrate(state);
  const meta = index.races.find((r) => r.round === round);

  const stopNarration = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    speechRef.current = null;
    setSpeaking(false);
  }, []);

  const speakRadio = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    stopNarration();
    const utterance = new SpeechSynthesisUtterance(radio.text);
    utterance.rate = 1.04;
    utterance.pitch = 1;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    speechRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, [radio.text, stopNarration]);

  /* Voice mode is intentionally opt-in: a live lap replay otherwise produces
     an unreliable pile-up of radio messages. Each new briefing replaces the
     last one, just like the engineer channel would. */
  useEffect(() => {
    if (voiceMode) speakRadio();
    return () => stopNarration();
  }, [voiceMode, radio.text, speakRadio, stopNarration]);

  useEffect(() => () => stopNarration(), [stopNarration]);

  if (err) {
    return (
      <section>
        <SurfaceHead n="1" title="Race replay" />
        <p className="text-[14px] text-dim">
          Could not read the replay feed for round {round}. {err}
        </p>
      </section>
    );
  }

  return (
    <section>
      <SurfaceHead
        n="1"
        title="Race replay"
        lede="Choose an event, scrub a lap, and read the decision in context. The replay keeps every timing row on screen—even the laps this model will not use—so the model’s boundary is visible rather than hidden."
      />

      <div className="replay-console bg-raise p-4 sm:p-5">
        <div className="grid gap-4 md:grid-cols-[minmax(220px,0.9fr)_minmax(220px,1.2fr)_auto] md:items-end">
          <div>
            <div className="mb-1.5 text-[11px] font-medium tracking-[0.12em] text-faint">EVENT</div>
            <Select
              ariaLabel="Event"
              value={String(round)}
              onChange={(v) => {
                setPlaying(false);
                setFocus(null);
                setRound(Number(v));
              }}
              options={index.races.map((r) => ({
                value: String(r.round),
                label: r.event.replace(" Grand Prix", ""),
              }))}
            />
          </div>
          {replay && (
            <div>
            <div className="mb-1.5 flex items-baseline justify-between gap-4">
              <span className="text-[11px] font-medium tracking-[0.12em] text-faint">TIMELINE</span>
              <span className="num font-mono text-[14px] text-flag">
                {lap} / {replay.laps}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={replay.laps}
              step={1}
              value={lap}
              aria-label="Lap"
              onChange={(e) => {
                setPlaying(false);
                setLap(Number(e.target.value));
              }}
            />
            </div>
          )}
          <div className="flex items-center gap-3 md:justify-end">
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              disabled={!replay}
              className="replay-play border border-flag px-4 py-2 text-[12px] font-semibold tracking-[0.08em] text-flag disabled:border-hair disabled:text-faint"
            >
              {playing ? "PAUSE" : "PLAY"}
            </button>
            <div className="num font-mono text-[11px] leading-snug text-faint">
              {replay ? <>{replay.rows} records<br />{replay.clean_rows} model-ready</> : "reading…"}
            </div>
          </div>
        </div>

        {replay && (
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-hair pt-3 text-[11.5px]">
              {statuses.map((code) => {
                const label = replay.track_status_codes[code] ?? `code ${code}`;
                const quiet = code === "1";
                return (
                  <span
                    key={code}
                    className={quiet ? "text-dim" : "text-tifosi"}
                  >
                    {label}
                  </span>
                );
              })}
              <span className="num font-mono text-faint">
                {clean.length} of {rows.length} laps usable
              </span>
              {pittedThisLap.length > 0 && (
                <span className="text-flag">
                  in the pit lane: {pittedThisLap.map((s) => s.driver).join(", ")}
                </span>
              )}
              {interrupted && (
                <span className="text-tifosi">
                  racing interrupted on this lap — nothing here is measured
                </span>
              )}
          </div>
        )}
      </div>

      {/* ---------------- the radio line ----------------
          One sentence, built from the state block by a template. Every number in
          it is computed in lib/model.js and is the same number the table shows. */}
      <aside className="mt-5 overflow-hidden border-l-2 border-flag bg-panel" aria-label="Race engineer radio">
        <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-start sm:p-5">
          <div className="relative shrink-0 self-start">
            <div className={`engineer-avatar ${speaking ? "engineer-avatar--speaking" : ""}`}>
              <img src={engineerPortrait} alt="Race engineer wearing a radio headset" />
            </div>
            <span className={`engineer-presence ${speaking ? "engineer-presence--live" : ""}`} aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] tracking-[0.16em] text-flag">ENGINEER RADIO</p>
                <p className="mt-0.5 text-[12.5px] text-dim">
                  Ava · race engineer
                  {state?.focus_driver ? (
                    <>
                      {" "}· to <span className="font-mono text-white">{state.focus_driver}</span>
                    </>
                  ) : null}
                </p>
              </div>
              {clean.length > 0 && (
                <select
                  aria-label="Focus driver"
                  className="w-auto text-[12px]"
                  value={focusDriver ?? ""}
                  onChange={(e) => setFocus(e.target.value)}
                >
                  {[...clean]
                    .sort((a, b) => a.position - b.position)
                    .map((r) => (
                      <option key={r.driver} value={r.driver}>
                        P{Math.round(r.position)} {r.driver}
                      </option>
                    ))}
                </select>
              )}
            </div>
            <p
              aria-live="polite"
              className={`mt-3 max-w-[70ch] text-[16px] leading-relaxed ${
                radio.source === "no_data" ? "text-dim" : "text-white"
              }`}
            >
              {radio.text}
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-hair pt-3">
              <button
                type="button"
                onClick={speaking ? stopNarration : speakRadio}
                className="inline-flex items-center gap-2 text-[12px] text-white hover:text-flag"
                aria-label={speaking ? "Stop race engineer narration" : "Play race engineer narration"}
              >
                <span className={`radio-icon ${speaking ? "radio-icon--live" : ""}`} aria-hidden="true">{speaking ? "■" : "▶"}</span>
                {speaking ? "Stop transmission" : "Play briefing"}
              </button>
              <label className="inline-flex cursor-pointer items-center gap-2 text-[12px] text-dim">
                <input
                  type="checkbox"
                  checked={voiceMode}
                  onChange={(e) => setVoiceMode(e.target.checked)}
                />
                Voice mode <span className="text-faint">(read new briefings)</span>
              </label>
              <span className="font-mono text-[10px] tracking-[0.1em] text-faint">
                {speaking ? "TRANSMITTING" : voiceMode ? "VOICE ARMED" : "TEXT CHANNEL"}
              </span>
            </div>
            {state?.flags?.length ? (
              <p className="mt-2.5 font-mono text-[11px] text-faint">{state.flags.join(" · ")}</p>
            ) : null}
          </div>
        </div>
      </aside>

      {/* ---------------- the lap ---------------- */}
      {replay && (
        <div className="mt-5 overflow-x-auto bg-panel p-4 sm:p-5">
          <table className="w-full min-w-[620px] text-[13px]">
            <thead>
              <tr className="text-left text-[11px] text-faint">
                <th className="pb-2 font-normal">Pos</th>
                <th className="pb-2 font-normal">Driver</th>
                <th className="pb-2 font-normal">Tyre</th>
                <th className="pb-2 text-right font-normal">Age</th>
                <th className="pb-2 text-right font-normal">Lap time</th>
                <th className="pb-2 text-right font-normal">Down on fresh</th>
                <th className="pb-2 text-right font-normal">A stop is worth</th>
                <th className="pb-2 pl-4 font-normal">Status</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {[...rows]
                .sort((a, b) => (a.position ?? 99) - (b.position ?? 99))
                .map((r) => {
                  const pair = `${r.compound}>HARD`;
                  const priced = r.clean && M.hasPair(pair);
                  const pitting = pittedThisLap.some((s) => s.driver === r.driver);
                  return (
                    <tr
                      key={`${r.driver}-${r.lap}`}
                      className={`border-t border-hair ${r.clean ? "" : "text-faint"} ${
                        r.driver === focusDriver ? "bg-raise" : ""
                      }`}
                    >
                      <td className="num py-1.5">{r.position ?? "—"}</td>
                      <td className="py-1.5">
                        <button
                          type="button"
                          onClick={() => r.clean && setFocus(r.driver)}
                          className={r.clean ? "hover:text-flag" : "cursor-default"}
                        >
                          {r.driver}
                        </button>
                      </td>
                      <td className="py-1.5">
                        <Pill compound={r.compound} />
                      </td>
                      <td className="num py-1.5 text-right">{r.tyre_age ?? "—"}</td>
                      {/* Trap 3. A null time renders as a dash and the row survives. */}
                      <td className="num py-1.5 text-right">
                        {r.lap_time_s == null ? "—" : fmt(r.lap_time_s, 3)}
                      </td>
                      <td className={`num py-1.5 text-right ${r.clean ? "text-white" : ""}`}>
                        {r.clean ? fmt(M.degVsFresh(r.tyre_age), 2) : "—"}
                      </td>
                      <td className={`num py-1.5 text-right ${priced ? "text-flag" : ""}`}>
                        {priced ? fmt(M.step0(pair, meta.track_temp_c), 2) : "—"}
                      </td>
                      <td className="py-1.5 pl-4 text-[11.5px]">
                        {pitting ? (
                          <span className="text-flag">pit stop</span>
                        ) : r.clean ? (
                          <span className="text-faint">—</span>
                        ) : (
                          <span className="text-tifosi">{excuse(r)}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          {rows.length === 0 && (
            <p className="text-[13.5px] text-dim">
              No rows recorded on this lap in the feed.
            </p>
          )}
        </div>
      )}

      {stopsSoFar.length > 0 && (
        <div className="mt-5 bg-panel p-5">
          <h3 className="mb-1 text-[15px] font-semibold">Stops up to this lap</h3>
          <p className="mb-3 text-[12.5px] leading-relaxed text-faint">
            {stopsSoFar.length} of {race.stops.length} at this event. The rest have not happened yet
            on lap {lap}, so they are not on screen — the file knows the whole race and the replay is
            not allowed to.
          </p>
          <ul className="grid gap-x-8 gap-y-1 font-mono text-[12.5px] sm:grid-cols-2">
            {[...stopsSoFar]
              .sort((a, b) => b.pit_lap - a.pit_lap)
              .slice(0, 10)
              .map((s, i) => (
                <li key={`${s.driver}-${s.pit_lap}-${i}`} className="flex justify-between gap-3">
                  <span className="text-dim">
                    L{s.pit_lap} {s.driver} {s.pair.replace(">", " → ")}
                  </span>
                  <span className="num text-white">{signed(s.step_obs_s, 2)} s</span>
                </li>
              ))}
          </ul>
        </div>
      )}

      <div className="mt-5 space-y-5">
        <Limitation title="The track temperature here never changes">
          One number per event, the race mean, used on every lap of the replay. Real track
          temperature moves through a race and ours does not know it. Any sentence on this surface
          that sounded like the track was heating up would be invented, so none of them say it.
        </Limitation>
        <Limitation title="Nothing here measures the gap between two cars">
          The dataset has lap times and positions, not intervals. The engineer line prices a stop
          from a standing assumption of {fmt(1.5, 1)} s to the car ahead, carried over from surface
          two, where you set it yourself.
        </Limitation>
      </div>

      <Source>
        replay/R{String(round).padStart(2, "0")}.json — {replay?.rows ?? "…"} rows across{" "}
        {replay?.laps ?? "…"} laps, of which {replay?.clean_rows ?? "…"} are green-flag racing laps.
        Pit stops and the observed step across each one come from races/R
        {String(round).padStart(2, "0")}.json. {replay ? `Scheduled ${pl(replay.scheduled_laps, "lap")}.` : ""}
      </Source>
    </section>
  );
}
