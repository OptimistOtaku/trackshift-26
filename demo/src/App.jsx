import { useEffect, useMemo, useState } from "react";
import { getIndex, getModel } from "./lib/data.js";
import { makeModel, fmt } from "./lib/model.js";
import SignFlip from "./surfaces/SignFlip.jsx";
import Undercut from "./surfaces/Undercut.jsx";
import Replay from "./surfaces/Replay.jsx";
import Validation from "./surfaces/Validation.jsx";

/* Replay is the product experience. The evidence and calculator stay one key
   away, but a new visitor should land in the race, not in an explanation of it. */
const SURFACES = [
  { n: "1", key: "replay", label: "Race replay", Component: Replay },
  { n: "2", key: "undercut", label: "Undercut", Component: Undercut },
  { n: "3", key: "flip", label: "Why it works", Component: SignFlip },
  { n: "4", key: "validation", label: "Out of sample", Component: Validation },
];

export default function App() {
  const [index, setIndex] = useState(null);
  const [model, setModel] = useState(null);
  const [error, setError] = useState(null);
  const [active, setActive] = useState("replay");

  useEffect(() => {
    Promise.all([getIndex(), getModel()])
      .then(([i, m]) => {
        setIndex(i);
        setModel(m);
      })
      .catch((e) => setError(e.message));
  }, []);

  /* 1–4 jump between surfaces. On stage a keystroke is more reliable than a
     trackpad, and the rail is numbered so the shortcut is discoverable. */
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = e.target?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const hit = SURFACES.find((s) => s.n === e.key);
      if (hit) setActive(hit.key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const M = useMemo(() => (model ? makeModel(model) : null), [model]);

  if (error) {
    return (
      <main className="mx-auto max-w-[68ch] px-6 py-24">
        <h1 className="mb-3 text-[22px] font-semibold">Data files not found</h1>
        <p className="mb-5 text-[14.5px] leading-relaxed text-dim">
          This page reads every number from <code className="font-mono text-white">artifacts/demo</code>{" "}
          and computes nothing of its own. To serve them, run{" "}
          <code className="font-mono text-flag">npm run dev</code> from{" "}
          <code className="font-mono text-white">demo/</code>, or serve the repo root and open{" "}
          <code className="font-mono text-white">demo/dist/</code>.
        </p>
        <pre className="overflow-x-auto bg-panel p-4 font-mono text-[12px] whitespace-pre-wrap text-faint">
          {error}
        </pre>
      </main>
    );
  }

  if (!index || !M) {
    return (
      <main className="px-6 py-24">
        <p className="font-mono text-[13px] text-faint">Reading artifacts…</p>
      </main>
    );
  }

  const h = index.headline;
  const Active = SURFACES.find((s) => s.key === active).Component;

  return (
    <div className="min-h-screen">
      {/* ---------------- masthead ----------------
          The claim is set as one sentence with the measured quantities inline
          in mono yellow. A hero number in a box would say nothing about what
          was measured; a sentence that has to carry its own figures cannot
          overclaim without it being visible. */}
      <header className="border-b border-hair px-6 pt-10 pb-8 md:px-10">
        <div className="mx-auto max-w-[1180px]">
          <div className="mb-6 flex items-baseline gap-4">
            <span className="text-[15px] font-bold tracking-[0.22em]">PITWALL</span>
            <span className="num font-mono text-[12px] text-faint">
              {index.season} season · built {index.generated}
            </span>
          </div>

          <p className="mb-3 font-mono text-[11px] tracking-[0.18em] text-flag">
            LIVE RACE REPLAY · 12 EVENTS
          </p>
          <h1 className="max-w-[24ch] text-[40px] leading-[1.06] font-semibold tracking-[-0.03em] md:text-[58px]">
            Replay the race. See what a fresh tyre buys <span className="text-dim">before the call.</span>
          </h1>

          <p className="mt-5 max-w-[74ch] text-[15px] leading-relaxed text-dim">
            Scrub every recorded lap, follow the cars on track, and price a stop from the same
            fitted model used throughout the season. A fresh tyre is worth{" "}
            <span className="num font-mono text-flag">{fmt(M.raw.intercept, 2)} s/lap</span> at the
            reference condition. The value is measured across{" "}
            <span className="num font-mono text-white">{h.stops}</span> real stops from{" "}
            <span className="num font-mono text-white">{h.events}</span> events by reading the step
            in lap time across the stop itself.
          </p>
        </div>
      </header>

      {/* ---------------- timing strip ----------------
          Persistent, because the honest numbers should be on screen while the
          interesting numbers are being discussed, not on a later slide. */}
      <div className="border-b border-hair bg-panel px-6 md:px-10">
        <div className="mx-auto grid max-w-[1180px] grid-cols-2 gap-x-8 gap-y-3 py-3 md:grid-cols-5">
          <Stat label="Out-of-sample RMSE" value={fmt(h.rmse_s, 2)} unit="s" />
          <Stat label="Season-mean baseline" value={fmt(h.baseline_rmse_s, 2)} unit="s" dim />
          <Stat label="Events beaten" value={`${h.events_won}/${h.events_compared}`} />
          <Stat label="Calibration slope" value={fmt(h.calib_slope, 2)} />
          <Stat label="Pit loss, median" value={fmt(index.pit_loss.season_median_s, 1)} unit="s" dim />
        </div>
      </div>

      {/* ---------------- body ---------------- */}
      <div className="mx-auto flex max-w-[1180px] flex-col gap-8 px-6 py-9 md:flex-row md:gap-12 md:px-10">
        <nav aria-label="Surfaces" className="md:w-[168px] md:shrink-0">
          <ul className="flex gap-1 overflow-x-auto md:block md:gap-0">
            {SURFACES.map((s) => {
              const on = s.key === active;
              return (
                <li key={s.key}>
                  <button
                    type="button"
                    onClick={() => setActive(s.key)}
                    aria-current={on ? "page" : undefined}
                    className={`flex w-full items-baseline gap-2.5 px-2 py-2 text-left text-[14px] whitespace-nowrap transition-colors md:border-l-2 ${
                      on
                        ? "border-flag bg-raise text-white md:bg-transparent"
                        : "border-transparent text-dim hover:text-white"
                    }`}
                  >
                    <span className={`num font-mono text-[12px] ${on ? "text-flag" : "text-faint"}`}>
                      {s.n}
                    </span>
                    {s.label}
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 hidden text-[11.5px] leading-relaxed text-faint md:block">
            Press 1–4 to move between views.
          </p>
        </nav>

        <main className="min-w-0 flex-1">
          <Active M={M} index={index} />
        </main>
      </div>

      <footer className="border-t border-hair px-6 py-8 md:px-10">
        <p className="mx-auto max-w-[1180px] text-[12px] leading-relaxed text-faint">
          Every figure on this page is read from <span className="font-mono">artifacts/demo</span> and
          recomputed in the browser. No network calls, no model inference, no API key. Lap data from
          FastF1; in-laps, out-laps, safety-car and deleted laps are filtered out before anything is
          measured.
        </p>
      </footer>
    </div>
  );
}

function Stat({ label, value, unit, dim = false }) {
  return (
    <div className="flex items-baseline justify-between gap-3 md:block">
      <div className="text-[11px] text-faint">{label}</div>
      <div className={`num font-mono text-[15px] ${dim ? "text-dim" : "text-white"}`}>
        {value}
        {unit ? <span className="text-faint"> {unit}</span> : null}
      </div>
    </div>
  );
}
