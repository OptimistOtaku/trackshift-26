/* ===================================================================== *
 *  Shared surface furniture.
 *
 *  Shape carries meaning here, because yellow and red each do two jobs:
 *    bare yellow text/stroke  a number we measured, or a live control
 *    filled yellow pill       the MEDIUM compound
 *    bare red text/stroke     a wrong-signed number, or the naive fit
 *    filled red pill          the SOFT compound
 *    1px red full border      a limitation — the only full border on the page
 * ===================================================================== */

import { fmt, signed } from "../lib/model.js";

/* Pirelli's own encoding, which happens to be exactly the palette we were
   asked for: SOFT red, MEDIUM yellow, HARD white. Nothing invented. */
const COMPOUND = {
  SOFT: { bg: "var(--color-tifosi)", fg: "#ffffff" },
  MEDIUM: { bg: "var(--color-flag)", fg: "#000000" },
  HARD: { bg: "#ffffff", fg: "#000000" },
};

export function Pill({ compound, className = "" }) {
  const key = String(compound ?? "").toUpperCase();
  const c = COMPOUND[key];
  if (!c) {
    // INTERMEDIATE, WET, or a null compound. Outline, never guessed into one
    // of the three — the model has no pair for it and neither has the pill.
    return (
      <span
        className={`inline-block px-1.5 py-px text-[10px] tracking-wide text-dim ring-1 ring-hair ${className}`}
      >
        {key || "—"}
      </span>
    );
  }
  return (
    <span
      className={`inline-block px-1.5 py-px text-[10px] font-semibold tracking-wide ${className}`}
      style={{ background: c.bg, color: c.fg }}
    >
      {key}
    </span>
  );
}

/* A number that was measured or computed. Mono, tabular, sign printed. */
export function Num({ value, dp = 2, sign = false, unit, tone = "white", className = "" }) {
  const colour =
    tone === "flag"
      ? "text-flag"
      : tone === "tifosi"
        ? "text-tifosi"
        : tone === "dim"
          ? "text-dim"
          : "text-white";
  return (
    <span className={`num font-mono ${colour} ${className}`}>
      {sign ? signed(value, dp) : fmt(value, dp)}
      {unit ? <span className="text-faint"> {unit}</span> : null}
    </span>
  );
}

/* The one thing on this page allowed a full border. A border means: we tested
   this and it did not survive, and it is on screen anyway. */
export function Limitation({ title, children }) {
  return (
    <div className="border border-tifosi p-4">
      <div className="mb-1.5 font-semibold text-tifosi">{title}</div>
      <div className="max-w-[68ch] text-[13.5px] leading-relaxed text-dim">{children}</div>
    </div>
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-[12.5px] text-dim">{label}</span>
        {hint ? <span className="num font-mono text-[12.5px] text-flag">{hint}</span> : null}
      </div>
      {children}
    </label>
  );
}

export function Slider({ min, max, step = 1, value, onChange, ariaLabel }) {
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      aria-label={ariaLabel}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  );
}

export function Select({ value, onChange, options, ariaLabel }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={ariaLabel}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Panel({ children, className = "" }) {
  return <div className={`bg-panel p-5 ${className}`}>{children}</div>;
}

/* Surface heading. Numbered because JUDGE_QA section 4 is a rehearsed
   sequence that is actually walked in order on stage — not decoration. */
export function SurfaceHead({ n, title, lede }) {
  return (
    <header className="mb-6">
      <div className="flex items-baseline gap-3">
        <span className="num font-mono text-[13px] text-faint">{n}</span>
        <h2 className="text-[26px] leading-tight font-semibold tracking-[-0.01em]">{title}</h2>
      </div>
      {lede ? (
        <p className="mt-2 ml-[calc(1ch+0.75rem)] max-w-[70ch] text-[14.5px] leading-relaxed text-dim">
          {lede}
        </p>
      ) : null}
    </header>
  );
}

/* Provenance line. Every surface ends with where its numbers came from. */
export function Source({ children }) {
  return (
    <p className="mt-4 max-w-[74ch] text-[12px] leading-relaxed text-faint">{children}</p>
  );
}
