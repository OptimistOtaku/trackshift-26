/* ===================================================================== *
 *  Data access. Static JSON only — nothing here touches the network beyond
 *  the local server, and no API key exists anywhere in this app.
 *
 *  Root resolution tries three locations in order so the build works however
 *  it ends up being served on the day:
 *    1. vite publicDir (../artifacts/demo) — dev server and dist/
 *    2. one level up    — demo/ served from the repo root
 *    3. two levels up   — demo/dist/ served from the repo root
 * ===================================================================== */

const CANDIDATE_ROOTS = [
  import.meta.env.BASE_URL ?? "/",
  "../artifacts/demo/",
  "../../artifacts/demo/",
];

let rootPromise = null;
const cache = new Map();

async function fetchJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
  return res.json();
}

function resolveRoot() {
  if (rootPromise) return rootPromise;
  rootPromise = (async () => {
    const tried = [];
    for (const root of CANDIDATE_ROOTS) {
      try {
        await fetchJSON(`${root}index.json`);
        return root;
      } catch (err) {
        tried.push(`  ${root}index.json — ${err.message}`);
      }
    }
    throw new Error(`Could not find artifacts/demo. Tried:\n${tried.join("\n")}`);
  })();
  return rootPromise;
}

export async function getJSON(path) {
  if (cache.has(path)) return cache.get(path);
  const promise = resolveRoot().then((root) => fetchJSON(root + path));
  cache.set(path, promise);
  // A rejected promise must not be cached, or a transient failure is permanent.
  promise.catch(() => cache.delete(path));
  return promise;
}

const rid = (round) => `R${String(round).padStart(2, "0")}.json`;

export const getIndex = () => getJSON("index.json");
export const getModel = () => getJSON("model.json");

/* races/ — the fitting table. Filtered to clean green-flag laps, so it has
   holes. Correct for `stops[]` and the validation scatter. */
export const getRace = (round) => getJSON(`races/${rid(round)}`);

/* replay/ — every lap FastF1 recorded, zero blank laps, per-lap flags.
   This is what the scrubber reads. Its clean:true rows reproduce races/
   laps_data row for row, so the two feeds differ by nothing but the filter. */
export const getReplay = (round) => getJSON(`replay/${rid(round)}`);

/* commentary/ — pre-generated radio lines, per RACE_ENGINEER.md section 5.1.
   Not exported yet. Resolves to null rather than throwing, so the panel falls
   straight to the deterministic template and nothing on screen says "error".
   When Aditya ships scripts/gen_commentary.py this starts working with no
   change here. */
export async function getCommentary(round) {
  try {
    return await getJSON(`commentary/${rid(round)}`);
  } catch {
    return null;
  }
}
