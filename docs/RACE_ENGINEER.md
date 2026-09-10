# Race engineer - LLM commentary layer

A radio voice over the replay. It reads the numbers the model already computed and says them
like an engineer would. That is the entire feature.

**It narrates numbers. It never produces them.** Every figure it utters is computed by
`src/pitwall/` and handed to it as input. It is not allowed to reason about tyre physics,
because if it is, it will invent a plausible number, and a plausible number that nothing
validated is exactly the thing this project exists to argue against. Turn the feature off and
every number on the dashboard is unchanged - that is the test of whether the boundary is in
the right place.

Read `docs/DEMO_CONTRACT.md` for the data and `docs/DEMO_BRIEF.md` for the copy rules first.
This document assumes both.

---

## 0. Architecture: offline first, on purpose

The obvious build is a browser that calls the Anthropic API on every scrub. Do not build that.
Three things are wrong with it on a stage in Mohali:

1. It needs an API key in client-side JavaScript. That key is then in the repo, in the browser
   devtools, and on the projector.
2. It puts a network round trip between the judge's mouse and the screen, on venue wifi.
3. It makes the commentary non-deterministic at the exact moment we least want surprises.

So the replay commentary is **pre-generated on a laptop with working wifi, validated, and
shipped as static JSON** next to the rest of `artifacts/demo/`. At demo time the browser looks
up a lap in a dictionary. No key, no network, no latency, and the text has already been checked
against the numbers.

```
BUILD TIME (Friday, on wifi)          DEMO TIME (Saturday, no wifi needed)
------------------------------        -----------------------------------
state block per lap                   fetch artifacts/demo/commentary/R08.json
  -> Claude Haiku 4.5                 look up lap -> render text
  -> numeric validator                miss -> deterministic template
  -> commentary/R08.json              no data for lap -> static caption
```

Label it on screen. A small caption - "commentary written offline by Claude Haiku 4.5 from the
numbers on this page; it computes nothing" - is more honest than implying a live model, and it
is the answer to the first question a judge will ask anyway. Pretending it is live and being
caught is the only bad outcome here.

The one thing that genuinely cannot be pre-generated is a line about an undercut the user just
dialled in on the sliders, because the inputs are continuous. That surface gets a deterministic
template by default (section 5.4). It is optional whether an LLM ever touches it.

---

## 1. The state block

One JSON object per lap. It is the model's entire universe: if a fact is not in here, the model
does not know it and is forbidden from saying it.

### 1.1 Schema

`schema` is `"pitwall.race_engineer.state/1"`. Bump it if you change field names.

**Race level** - all from `index.json` / the race file header.

| Field | Type | Source | Notes |
|---|---|---|---|
| `round` | int | `R08.json:round` | |
| `event` | string | `R08.json:event` | |
| `lap` | int | scrubber position | coerce; `laps_data.lap` is a float |
| `race_laps` | int | `R08.json:laps` | |
| `track_temp_c` | float 1dp | `R08.json:track_temp_c` | see 1.3 - this is a race mean |
| `track_temp_basis` | string | constant | `"race mean; constant for every lap of this replay"` |
| `pit_loss_s` | float 2dp | `R08.json:pit_loss_s` | measured, `build_pitloss.py` |
| `focus_driver` | string | UI | whose radio this is |
| `target_compound` | string | UI dropdown | what a stop would fit; default `"HARD"` |

**Per driver** - one entry in `drivers[]`, built from the `laps_data` rows where
`lap === L`, sorted by `position`. Cap it (section 1.4).

| Field | Type | Source | Notes |
|---|---|---|---|
| `driver` | string | `laps_data.driver` | measured |
| `position` | int | `laps_data.position` | measured; coerce from float |
| `compound` | string | `laps_data.compound` | measured |
| `tyre_age` | int | `laps_data.tyre_age` | measured; coerce from float |
| `lap_time_s` | float 3dp | `laps_data.lap_time_s` | measured |
| `deg_vs_fresh_s` | float 2dp | computed | `phi(tyre_age) - phi(fresh_age)`; clamp to 0 below `fresh_age`, see 1.5 |
| `deg_marginal_s` | float 3dp | computed | optional; `b1 + 2*b2*age`, 0 past `peak_age` |
| `tyre_saturated` | bool | computed | `tyre_age >= peak_age` (21.46) |
| `stop_gain_s` | float 2dp | computed | `step0(compound + ">" + target_compound)` |
| `target_pair` | string | derived | e.g. `"MEDIUM>HARD"`; must be a key of `model.pairs` |
| `pitted_this_lap` | bool | `stops[]` | `stops.some(s => s.pit_lap === L && s.driver === d)` |

**Undercut** - one `undercut` object for `focus_driver` against the car in `position - 1`.
Omit the whole object if the focus driver is P1 or the car ahead has no row this lap.
Fields follow `strategy.summarise_undercut` and the JS in DEMO_BRIEF section 3.

| Field | Type | Notes |
|---|---|---|
| `me`, `rival` | string | driver codes |
| `gap_ahead_s` | float 1dp | **UI input, not measured** - see 1.2 |
| `gap_source` | string | always `"ui_input"` |
| `pair` | string | `me.compound + ">" + target_compound` |
| `my_tyre_age`, `rival_tyre_age` | int | measured |
| `step0_s_per_lap` | float 2dp | validated first-lap advantage for this pair and temp |
| `first_lap_gain_s` | float 2dp | `rows[0].time_gained_s` - the hero number |
| `works` | bool | any row with `ahead` |
| `needs_them_out_laps` | int / null | first `k` with `ahead` |
| `tyre_deficit_laps` | int / null | equals `needs_them_out_laps`; **the cost** |
| `rows` | array | `k = 1..3` only (see 1.4); each `{they_respond_after_laps, time_gained_s, gap_after_s, ahead}` |
| `extrapolating` | bool | `my_tyre_age > max_age_seen` (50) |

**Flags** - `flags[]`, an array of tokens from a closed vocabulary. The UI decides these; the
model narrates them and may not infer any others.

| Token | Set when |
|---|---|
| `PIT_STOPS_THIS_LAP` | any driver in `drivers[]` has `pitted_this_lap` |
| `FOCUS_PITTED_THIS_LAP` | the focus driver has `pitted_this_lap` |
| `RIVAL_PITTED_THIS_LAP` | the car ahead has `pitted_this_lap` |
| `TYRE_PAST_SATURATION` | focus driver `tyre_saturated` |
| `EXTRAPOLATING` | `undercut.extrapolating` |
| `UNDERCUT_NOT_AVAILABLE` | `undercut.works === false` |

**Provenance** - constant, from `index.json:headline`. Present so the model can answer "where
does that number come from" without inventing a citation, and so the validator whitelists these
digits.

```json
"provenance": { "stops_analysed": 288, "events": 12, "oos_rmse_s": 0.96, "calib_slope": 0.79 }
```

### 1.2 The gap is an input, not a measurement

There is no gap field in `artifacts/demo/`. You cannot derive one from `laps_data` either:
`clean_laps` drops in-laps, out-laps, non-green and deleted laps, so cumulative lap-time sums
are not comparable between cars. At Austria lap 16, summing every clean lap gives RUS 1160.5 s
and VER 1088.1 s - a 72 s "gap" that is entirely VER missing lap 1 from the file.

So `gap_ahead_s` comes from the slider the undercut calculator already has (DEMO_BRIEF section
3, range 0-5 s, default 1.5). It is carried with `gap_source: "ui_input"` and the system prompt
tells the model it is the operator's assumption. Quote it; never call it measured.

### 1.3 Causality: three ways to accidentally leak the future

The replay is a time machine and the race file contains the whole race. Three specific leaks,
all of which a judge can catch:

1. **`stops[]` knows the future.** At Austria lap 16 the array already says VER pits on lap 17.
   Pass the whole array and the model will say "you're boxing next lap". Filter to
   `s.pit_lap <= L` before deriving anything, and only surface `pit_lap === L`.
2. **`track_temp_c` is a race mean** (`export_demo.py`: `race["TrackTemp"].mean()`). At lap 10
   it technically knows the afternoon. It is the same value the fitted model was trained on, so
   we keep it and label it: it is a race constant, it does not move during the replay, and the
   model must never describe the track as heating up or cooling down. (`stopvalue.stop_table`
   makes the same choice for the same reason.)
3. **Never pass `laps_data` rows with `lap > L`.** Obvious, and still worth a unit test.

### 1.4 What we deliberately do not pass

| Not passed | Why |
|---|---|
| `fuel_kg` | the deployed spec is pair + temp + traffic; fuel is upstream in the pace model, not in `step0`. Passing it invites fuel commentary we cannot back. |
| `frac_close` / any traffic term | the model's `d_close` is `close_old - close_new`, a difference **across** the stop. Half of it is in the future during a replay. The demo sets `d_close = 0` (the sample mean, i.e. "typical"), exactly as `step0()` in DEMO_BRIEF does. There is no honest per-lap traffic number to narrate. |
| Safety-car probability | not fitted, and cannot be from 12 races at 12 circuits. If the UI ever gains an SC slider it is the user's assumption and stays out of the model's mouth. |
| Any pit-window / payback output | see section 3 and `strategy.py`. |
| All 20 drivers | tokens and latency, and the model gets vaguer the more rows it must choose between. Austria lap 16 has 20 rows and 14 of them are identical 16-lap mediums. Selection rule: **top 5 by position, plus anyone with `pitted_this_lap`, plus the fastest lap time this lap if not already in.** Deterministic, usually 5-7 rows, and it always includes the two cars a stop is actually about. |
| `rows[k]` for k > 3 | the interesting answer is always k = 1 or 2. Eight rows is 5x the tokens for narration that never uses them. The dashboard still computes and shows all eight. |

### 1.5 Rounding: one formatter, both surfaces

The state block carries numbers **already rounded to the precision we are willing to hear on
air**, and the model is forbidden from rounding further. That means the dashboard and the state
builder must use the same formatter, or the voice will say 0.51 while the panel shows 0.5097
and a judge will notice the disagreement.

```js
const fmt = (x, dp) => Number(x.toFixed(dp));   // use for BOTH the DOM and the state block
```

Precisions: lap times 3dp, seconds-per-lap 2dp, `deg_marginal_s` 3dp, track temp 1dp, gap 1dp.

One clamp goes with it. `deg_vs_fresh_s` is measured against `fresh_age = 3`, not against lap
one of a stint, because a brand-new tyre is not at its quickest on its first flying lap. So a
driver two laps into a stint computes to a **negative** number - SAI at Austria lap 16 is on a
2-lap medium and comes out at -0.06. "You are 0.06 s/lap better than fresh" is not a sentence
anyone should hear on the radio. Clamp `deg_vs_fresh_s` to `0.00` whenever
`tyre_age <= fresh_age`, and carry `deg_reference_age: 3` in the block so the number has a
stated baseline if anyone asks.

### 1.6 Worked example - Austria, lap 16

Austria lap 16 is the demo lap. RUS leads VER, both on 16-lap-old MEDIUMs: the textbook
undercut fight the module docstring describes - two cars on the same compound at a similar age,
one blinks first, which is precisely the case the model handles best. In the real race VER
boxed on lap 17 and RUS on lap 18. BOR is in the pit lane on this lap, so the flag mechanism
has something to narrate. HAM, P8 on 4-lap-old HARDs after stopping on lap 11, is lapping
quicker than the leader, which is what a stop being worth 1.63 s/lap looks like from the
outside.

Every value below is computed from the shipped `artifacts/demo/model.json` and
`artifacts/demo/races/R08.json` as of 11 Sep. **If `model.json` is refit these change** - see
failure mode 13, which has already happened once.

```json
{
  "schema": "pitwall.race_engineer.state/1",
  "round": 8,
  "event": "Austrian Grand Prix",
  "lap": 16,
  "race_laps": 71,
  "track_temp_c": 51.1,
  "track_temp_basis": "race mean; constant for every lap of this replay",
  "pit_loss_s": 21.69,
  "focus_driver": "VER",
  "target_compound": "HARD",
  "deg_reference_age": 3,
  "drivers": [
    { "driver": "RUS", "position": 1, "compound": "MEDIUM", "tyre_age": 16,
      "lap_time_s": 72.780, "deg_vs_fresh_s": 0.51, "deg_marginal_s": 0.018,
      "tyre_saturated": false, "stop_gain_s": 1.63, "target_pair": "MEDIUM>HARD",
      "pitted_this_lap": false },
    { "driver": "VER", "position": 2, "compound": "MEDIUM", "tyre_age": 16,
      "lap_time_s": 72.626, "deg_vs_fresh_s": 0.51, "deg_marginal_s": 0.018,
      "tyre_saturated": false, "stop_gain_s": 1.63, "target_pair": "MEDIUM>HARD",
      "pitted_this_lap": false },
    { "driver": "ANT", "position": 3, "compound": "MEDIUM", "tyre_age": 16,
      "lap_time_s": 72.883, "deg_vs_fresh_s": 0.51, "deg_marginal_s": 0.018,
      "tyre_saturated": false, "stop_gain_s": 1.63, "target_pair": "MEDIUM>HARD",
      "pitted_this_lap": false },
    { "driver": "PIA", "position": 4, "compound": "MEDIUM", "tyre_age": 16,
      "lap_time_s": 73.179, "deg_vs_fresh_s": 0.51, "deg_marginal_s": 0.018,
      "tyre_saturated": false, "stop_gain_s": 1.63, "target_pair": "MEDIUM>HARD",
      "pitted_this_lap": false },
    { "driver": "NOR", "position": 5, "compound": "MEDIUM", "tyre_age": 16,
      "lap_time_s": 73.323, "deg_vs_fresh_s": 0.51, "deg_marginal_s": 0.018,
      "tyre_saturated": false, "stop_gain_s": 1.63, "target_pair": "MEDIUM>HARD",
      "pitted_this_lap": false },
    { "driver": "HAM", "position": 8, "compound": "HARD", "tyre_age": 4,
      "lap_time_s": 72.318, "deg_vs_fresh_s": 0.06, "deg_marginal_s": 0.057,
      "tyre_saturated": false, "stop_gain_s": 2.01, "target_pair": "HARD>HARD",
      "pitted_this_lap": false },
    { "driver": "BOR", "position": 10, "compound": "SOFT", "tyre_age": 16,
      "lap_time_s": 74.072, "deg_vs_fresh_s": 0.51, "deg_marginal_s": 0.018,
      "tyre_saturated": false, "stop_gain_s": 1.69, "target_pair": "SOFT>HARD",
      "pitted_this_lap": true }
  ],
  "undercut": {
    "me": "VER", "rival": "RUS",
    "gap_ahead_s": 1.5, "gap_source": "ui_input",
    "pair": "MEDIUM>HARD",
    "my_tyre_age": 16, "rival_tyre_age": 16,
    "step0_s_per_lap": 1.63,
    "first_lap_gain_s": 1.78,
    "works": true,
    "needs_them_out_laps": 1,
    "tyre_deficit_laps": 1,
    "rows": [
      { "they_respond_after_laps": 1, "time_gained_s": 1.78, "gap_after_s": -0.28, "ahead": true },
      { "they_respond_after_laps": 2, "time_gained_s": 3.50, "gap_after_s": -2.00, "ahead": true },
      { "they_respond_after_laps": 3, "time_gained_s": 5.17, "gap_after_s": -3.67, "ahead": true }
    ],
    "extrapolating": false
  },
  "flags": ["PIT_STOPS_THIS_LAP"],
  "provenance": { "stops_analysed": 288, "events": 12, "oos_rmse_s": 0.96, "calib_slope": 0.79 }
}
```

An acceptable reply to that block:

```
Russell's 1.5 up the road, same 16-lap medium. A stop is worth 1.78 on him the first lap
out. He has to stay out 1 lap, and you rejoin 1 lap older.
```

Every digit in that sentence - 1.5, 16, 1.78, 1, 1 - is copied from the block. Nothing was
worked out. Note what it does **not** say: it prices the stop, it does not call one. "Box now"
would be a pit-lap recommendation and is banned in section 2 and caught by the regex in
section 6.

---

## 2. The system prompt

Paste as-is. It is written to be repetitive about the number rule on purpose: the rule is
stated in the second paragraph and again as the last thing the model reads, because those are
the two positions that survive.

```text
You are the race engineer on a Formula 1 pit wall, talking to your driver over the radio
during a race replay. You are given a JSON state block for the current lap. You reply with
one to three short sentences of radio commentary. Nothing else.

THE ONE RULE THAT MATTERS: every number you say must already be in the state block, copied
exactly as it is written there. You do not calculate. You do not estimate. You do not round,
convert, add, subtract or combine numbers. You know nothing about tyre physics, lap times,
fuel, weather or strategy beyond what this block says about this lap. If a number is not in
the block, it does not exist and you must not say it.

The numbers in the block were measured across 288 real pit stops from the 2026 season and
validated out of sample. That is why they are allowed on the radio. Anything you produce
yourself has been validated by nobody and is not allowed on the radio.

WHAT THE FIELDS MEAN
  deg_vs_fresh_s        seconds per lap this driver is losing to tyre age, against a fresh
                        set. The reference is deg_reference_age laps old, not zero.
  deg_marginal_s        seconds per lap they lose by running one more lap (may be absent)
  stop_gain_s           seconds per lap a stop right now would buy, fitting target_compound
  tyre_saturated        true means the tyre is past the age where measured degradation stops
                        accumulating; it does not mean the tyre is fine
  lap_time_s            the lap they just did, measured
  pitted_this_lap       true means that car is in the pit lane on this lap. Report it as
                        something that is happening. Never guess who might stop next.
  track_temp_c          a race average, the same on every lap. Never say the track is heating
                        up, cooling down, or changing.
  undercut.gap_ahead_s  the gap, set by the operator on a slider. Quote it. Never call it
                        measured or observed.
  undercut.first_lap_gain_s     seconds gained on the rival on the first lap after stopping
  undercut.needs_them_out_laps  laps the rival must stay out for the undercut to clear
  undercut.tyre_deficit_laps    laps older your tyres will be once you have passed them
  undercut.works        false means it does not clear them; say so plainly
  extrapolating         true means this tyre is older than any tyre in the data. Say the
                        number is outside what we measured.
  flags                 events on this lap, already determined. Narrate these. Never infer
                        any event that is not in this list.
  provenance            where the numbers come from. Use only if asked.

WE DO NOT RECOMMEND A PIT LAP. Never tell the driver which lap to stop on. Never say "box
this lap", "box now", "stay out until lap N", "the window opens on lap N", or anything that
picks a lap. We built a pit-lap recommender and tested it against 288 real stops: it covered
68.4 percent of them versus 65.8 percent for a width-matched window simply placed mid-race, a
margin too small to lean on, and per event that mid-race constant tracked the chosen lap
better than our window did (MAE 4.9 versus 8.4 laps), so it added nothing over "pit halfway
through the race" and we cut it. You have
nothing to base a pit lap on. Never volunteer one. If you are asked for one, say that we do
not call the lap, we only price the stop.

WHEN YOU REPORT AN UNDERCUT, SAY THE COST IN THE SAME BREATH. An undercut that works still
leaves you on older tyres than the car you just passed. Whenever undercut.works is true you
must say tyre_deficit_laps alongside first_lap_gain_s. A gain quoted without its cost is a
sales pitch, not a call, and we do not make sales pitches.

WORDS YOU NEVER USE: "optimal strategy", "optimal", "best strategy", "AI-powered", "AI",
"machine learning", "95% accurate", "predicted lap time", "simulated race", "guaranteed".
We do not predict lap times and we do not simulate races. We price what a fresh tyre is
worth, which is a narrower claim and a much better supported one. Keep to that.

STYLE
  Radio. One to three sentences, 35 words maximum, no exceptions.
  Speak to the driver: "you", or the driver code. No greeting, no sign-off, no emoji.
  Situation, then the number, then the consequence. Flat and factual. No excitement.
  Write every number as digits, exactly as it appears in the block. Never spell a number
  out in words.
  Pick the single thing that matters this lap. Do not read the block back.
  Plain text. No markdown, no bullet points, no headings, no quotation marks.
  If there is no undercut object, do not mention undercuts at all.
  If nothing is happening, a plain tyre-state line is a complete and correct answer.

FINAL REMINDER, BECAUSE IT IS THE ONLY THING THAT MAKES THIS TOOL DEFENSIBLE: every digit
you type is copied from the state block. If you find yourself working something out, stop,
and say a number that is already there instead.
```

The user message is the state block JSON and nothing else. Keeping it pure means the cache key
is a function of the block alone.

---

## 3. Why the pit-lap prohibition is worded that hard

From `src/pitwall/strategy.py`, and it is worth being able to say this out loud on stage:

- The full-race optimum is **not identified** from this data. A constant per-lap benefit for
  fitting a quicker tyre makes total gain grow with laps remaining, so the objective falls
  monotonically in the pit lap and the optimiser says "stop on lap one". What stops that in
  reality is a compound-specific wear rate, and interacting age with compound over 288 stops
  and three compounds is collinear with stint position. It is not estimable here.
- The pit window **did not survive its own test**. 68.4 percent coverage against 288 real
  stops, leave-one-event-out, versus 65.8 percent for a width-matched mid-race window — a
  margin too small to lean on. What decides it is the per-event test: the mid-race constant
  tracks each event's median chosen lap better than the window centre does (r = +0.73, MAE 4.9
  laps versus r = +0.64, MAE 8.4 laps), and dividing race length out the window centre carries
  no information about where teams actually stopped (r = +0.08, p = 0.80). Both of its edges
  are arithmetic on race length, so it reproduces "mid-race" because that is all it knows.

An LLM that knows F1 knows that engineers call pit laps, and it will drift toward doing so
unless told not to, repeatedly and with the reason attached. The reason is in the prompt
because a rule with a reason survives paraphrase better than a bare prohibition.

What survives is the undercut, and it survives because of what it does not touch: the pit loss
cancels (both cars serve the same pit lane), race length never enters, and the horizon is one
to eight laps where the data is densest. That is the only strategic claim the voice is allowed
to make.

---

## 4. Model choice, parameters, latency

### Recommendation: Claude Haiku 4.5, `claude-haiku-4-5`

Four reasons, in the order they actually decided it:

1. **The task is not a reasoning task.** All the reasoning happened in `strategy.py`. What is
   left is turning three numbers and a driver code into one radio sentence under a hard style
   constraint - the class of work Haiku is built for. Sonnet's richer phrasing is capability
   spent on the one job we have explicitly forbidden: thinking about tyres.
2. **A bigger model is the bigger risk here, not the smaller one.** Sonnet 5 knows more about
   F1 strategy, which means more pull toward volunteering the pit lap we cut, more unprompted
   context ("mediums usually go 20-25 laps here"), more numbers that sound right. Our failure
   mode is fluent invention, and fluency is the thing the larger model has more of.
3. **Sonnet 5 rejects `temperature`.** Sampling parameters (`temperature`, `top_p`, `top_k`)
   were removed on Sonnet 5 and return a 400. We want an explicit low temperature to keep
   phrasing tight and reduce the chance of a rogue figure. Haiku 4.5 accepts sampling
   parameters. For this design that alone settles it.
4. **Latency.** Haiku 4.5 is the fastest model in the lineup, and although the demo path is
   pre-generated (so runtime latency is a dictionary lookup, not an API call), generation speed
   still decides whether we can regenerate all 740 laps of the season in a coffee break after a
   late change to `model.json`.

Cost is **not** an argument either way and should not be presented as one: $1.00 / $5.00 per
MTok for Haiku 4.5 against $2.00 / $10.00 for Sonnet 5, on a workload of a few hundred
thousand tokens. The whole season costs about a dollar on either.

`claude-haiku-4-5` is the documented alias. The pinned snapshot `claude-haiku-4-5-20251001`
resolves to the same model and is a defensible choice for a frozen demo; do not append a date
to any other model ID, since the other current IDs are complete as they stand.

### Request parameters

```python
import anthropic

client = anthropic.Anthropic()   # ANTHROPIC_API_KEY, or an `ant auth login` profile

msg = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=120,
    temperature=0.3,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": json.dumps(state, separators=(",", ":"))}],
)
text = next(b.text for b in msg.content if b.type == "text").strip()
```

| Parameter | Value | Why |
|---|---|---|
| `max_tokens` | 120 | The target output is 25-40 tokens. 120 is roughly 3x headroom, so a slightly wordy reply still ends on its own instead of being guillotined mid-sentence - a truncated radio line is the most obviously broken thing that can appear on stage. It is also a hard ceiling on a model that decides to lecture. Do not set it near the target: `max_tokens` is enforced, not advisory, and the model cannot see it. |
| `temperature` | 0.3 | 0.0 is tempting and wrong. Across 71 consecutive laps whose state blocks barely differ, greedy decoding writes near-identical sentences, and scrubbing through them reads like a stuck record. 0.3 varies the phrasing over the same facts. Determinism at demo time comes from the cache, not from the sampler, so we can afford the variety. Do not go above 0.5; that is where the invented numbers live. |
| `thinking` | omitted | Off by default on Haiku 4.5. Enabling it costs latency and buys nothing when the reasoning is already done in Python. |
| `output_config.effort` | do not send | `effort` errors on Haiku 4.5. It is a 4.6+ parameter. |
| `stream` | off for pre-generation | Outputs are tiny and it is a batch job. Only stream on the optional live path (5.4), where first-token time is what the user perceives. |
| `cache_control` | do not set | The minimum cacheable prefix on Haiku 4.5 is 4096 tokens. The system prompt is around 900. Caching will silently not engage and `usage.cache_read_input_tokens` will read 0 - that is expected, not a bug. Do not pad the prompt to reach the minimum; padding costs more latency than the cache saves. |

### Generation budget

740 laps across the 12 races. About 1600 input tokens (system ~900 plus a ~700-token state
block) and ~60 output tokens each: roughly 1.2M input and 45K output for the whole season, so
about **USD 1.40 for everything, and about 13 cents for Austria alone**. At 4-8 concurrent
requests the season takes a few minutes and one race takes well under one.

That budget is the real argument for pre-generation: it is cheap enough to generate every lap
of every race, which means the network is never in the demo path at all.

---

## 5. Offline fallback

Treat this as the primary path, not the backup. Assume the venue wifi is gone.

### 5.1 Cache file

One per race, alongside the rest of the demo data, so it is fetched exactly like everything
else and needs no new plumbing.

```
artifacts/demo/commentary/R08.json
```

```jsonc
{
  "schema": "pitwall.race_engineer.cache/1",
  "round": 8,
  "model": "claude-haiku-4-5",
  "generated": "2026-09-11",
  "prompt_sha256": "9f2c...",        // sha256 of SYSTEM_PROMPT; regenerate if it changes
  "model_sha256": "4b81...",         // sha256 of model.json; regenerate if it changes
  "focus_policy": "leader_fight",   // how focus_driver was chosen, see 5.2
  "target_compound": "HARD",
  "gap_assumption_s": 1.5,
  "laps": {
    "16": { "focus_driver": "VER", "rival": "RUS", "validated": true,
            "text": "Russell's 1.5 up the road, same 16-lap medium. A stop is worth 1.78 ..." },
    "24": { "focus_driver": null, "text": null, "reason": "no_green_laps" }
  }
}
```

Keys are lap numbers as strings - remember `laps_data.lap` arrives as a float, so index with
`String(Math.round(lap))`. Austria is about 15 KB.

`prompt_sha256` and `model_sha256` exist so neither a changed prompt nor a refit model can
silently ship against stale text. The generator writes both; a one-line check in the build
compares them and warns. See failure mode 13 - the model has already been refit once.

### 5.2 What to pre-generate

**Race:** R08, Austria. Beyond being the race DEMO_BRIEF already nominates, it has the cleanest
lap coverage of the twelve - only laps 24 and 25 have no representative green-flag laps at all,
and only lap 26 is thin (2 cars). Compare Monaco (R06), which has a twelve-lap hole from 60 to
71, Japan (R03), empty from 22 to 27, or Miami (R04), empty from 5 to 11. Only Barcelona (R07)
and Hungary (R11) have no holes at all. Generate the others if time allows; Austria is the one
that has to be right.

**Laps:** all 71. There is no point choosing a subset when the whole race costs 13 cents - a
judge who scrubs to lap 44 must not fall off the edge of a curated path.

**Focus driver:** one per lap, chosen by a deterministic policy so the cache key is stable.
`leader_fight`: the car running **second**, with the leader as its rival. The challenger is the
one with a reason to stop, and the leader can never be the focus driver anyway because the
undercut object needs a car ahead. Record the policy in the file. If the UI lets the user pick
a different focus driver, that is a cache miss and falls to the template - which is fine, and
is why the template has to be good.

**Gap:** the cached undercut lines assume `gap_ahead_s = 1.5`, recorded as `gap_assumption_s`.
Moving the slider is a cache miss by design; the slider surface is the template's job.

### 5.3 Generation script contract

`scripts/gen_commentary.py` (not written yet - this is its spec):

1. Load `model.json` and `races/R{NN}.json`.
2. For each lap `L` in `1..laps`: build the state block per section 1, applying the causality
   filters in 1.3. If there are no `laps_data` rows for `L`, write
   `{"focus_driver": null, "text": null, "reason": "no_green_laps"}` and move on - do not call
   the API for a lap with no data.
3. Call Haiku 4.5 with the parameters in section 4.
4. Run the validator in section 6. On failure, retry once with a corrective user message
   ("that reply contained a number not in the state block: X. Reply again, using only the
   numbers in the block."). On second failure, write the deterministic template text with
   `"validated": false, "source": "template"` and log the lap loudly.
5. Write the file after every lap, and skip laps already present on re-run. The script must be
   resumable: a rate limit at lap 60 should not cost the first 59.
6. Concurrency 4-8. The SDK already retries 429 and 5xx twice with backoff; catch
   `anthropic.RateLimitError`, `anthropic.APIStatusError` and `anthropic.APIConnectionError`
   separately so a network failure at build time is distinguishable from a bad request.
7. Print a summary: laps generated, laps validated, laps that fell back to the template, laps
   with no data. **If any lap failed validation, that is a bug in the prompt, not noise - fix
   the prompt and regenerate.**

### 5.4 Runtime lookup ladder

Every rung renders into the same slot with the same typography. Nothing on this ladder says
"error", shows a spinner that outlives a heartbeat, or changes the height of the panel.

1. **Cache hit** for `(round, lap, focus_driver)` - render `text`.
2. **Cache miss but a state block exists** - render the deterministic template. This covers a
   user-chosen focus driver, a moved gap slider, and a different target compound.
3. **No state block** (no `laps_data` rows for this lap: Austria 24 and 25) - render the fixed
   caption, not the template:

   > No representative green-flag laps recorded on this lap. In-laps, out-laps, safety-car and
   > deleted laps are filtered out before anything is measured.

   That is true, it is the same filtering that makes the model defensible, and it turns the one
   visibly empty moment in the replay into a point in our favour. Grey it, keep the panel the
   same size.
4. **Live API** - optional, off by default, never on the stage build. If you want it in
   development, put the key in a local proxy (`localhost`), never in client JS, and render the
   template immediately, then swap in the model text if it arrives inside 1200 ms. Optimistic
   render and upgrade-in-place: the user never waits, and a timeout is invisible because
   something correct was already on screen.

### 5.5 The deterministic templates

These are the floor. They are always correct, always instant, and they say the same numbers in
the same layout as the model does - so a judge cannot tell which rung of the ladder they are
looking at, and it does not matter if they can.

```js
const pl = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

// replay line, any lap with data
`P${d.position} ${d.driver}, ${d.compound.toLowerCase()} ${pl(d.tyre_age, "lap")} old, ` +
`${d.deg_vs_fresh_s} s/lap down on a fresh set. A stop now is worth ${d.stop_gain_s} s/lap.`

// undercut available
`Undercut on ${u.rival}: +${u.first_lap_gain_s} s on the first lap out from ${u.gap_ahead_s} s ` +
`behind. They have to stay out ${pl(u.needs_them_out_laps, "lap")}. ` +
`You rejoin ${pl(u.tyre_deficit_laps, "lap")} older than them.`

// undercut not available
`No undercut on ${u.rival} from ${u.gap_ahead_s} s: the stop is worth ` +
`${u.first_lap_gain_s} s on the first lap out, and that does not clear them.`
```

The undercut template states the cost in the same sentence as the gain, for the same reason the
prompt requires it of the model.

---

## 6. Output validation

Run at generation time, before anything reaches the cache file. Two layers.

**Numeric whitelist.** Walk the state block, collect every numeric leaf into a set, and add the
absolute value of each (the model may legitimately say "0.28 clear" where the block holds
-0.28). Then extract every numeric token from the reply and require each one to match.

```python
import re
NUM = re.compile(r"-?\d+(?:\.\d+)?")

def allowed_values(state) -> set[float]:
    out = set()
    def walk(o):
        if isinstance(o, bool):   return          # bool is an int in Python; skip it
        if isinstance(o, (int, float)): out.add(float(o)); out.add(abs(float(o)))
        elif isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
    walk(state)
    return out

def numbers_ok(text: str, allowed: set[float]) -> bool:
    for tok in NUM.findall(text):
        v = float(tok)
        if not any(abs(v - a) < 1e-9 for a in allowed):
            return False
    return True
```

This is the single highest-value guard in the design, and it catches the pit-lap failure for
free: "box on lap 22" fails because 22 is not in the block. It is also why the prompt insists
on digits rather than words - a spelled-out number would slip past the regex.

**Banned phrases.** Case-insensitive, over the reply:

```python
BANNED = re.compile(
    r"optimal|best strateg|ai[- ]powered|artificial intelligence|machine learning"
    r"|95%|predicted lap time|simulated race|guarantee"
    r"|\bbox\b|come in (now|this lap|next lap)"
    r"|pit (now|this lap|next lap|on lap)|stop (this lap|next lap|on lap)"
    r"|stay out (until|another|two|three)|window (opens|closes)|pit window"
    r"|i(?:'d)? recommend|we recommend|you should (pit|box|stop)",
    re.I)
```

Two deliberate pieces of discrimination in there, both of which will look like bugs to whoever
maintains it - do not "fix" them:

- **`\bbox\b` bans the imperative but not the description.** "Box now" and "box, box, box" are
  calls and are banned. "BOR boxes this lap" is a legitimate narration of `pitted_this_lap` and
  passes, because the word boundary does not match inside "boxes".
- **`stop (this lap|on lap)`, not `stop now`.** "A stop now is worth 1.63 s/lap" is the approved
  pricing copy from DEMO_BRIEF and must pass. "Stop on lap 30" is a call and must not. The line
  between them is imperative versus price, not the word "stop".

Both layers fail closed: retry once with the offending token quoted back, then fall through to
the template. Never ship an unvalidated line into the cache without marking it.

---

## 7. Failure modes

| # | Failure | How it shows up | Mitigation |
|---|---|---|---|
| 1 | **Hallucinated number** | "you're losing 0.4 a lap" when the block says 0.51; a judge checks it against the panel | Prompt states the rule twice, at the top and as the last line. Numeric whitelist (section 6) rejects any token not in the block, retries once, then falls to the template. Validation happens at build time, so a bad line cannot reach the stage. |
| 2 | **Contradicts the dashboard** | voice says 0.51, panel shows 0.5097 or 0.5 | One formatter (`fmt`, section 1.5) feeds both the DOM and the state block. The block carries display-precision values and the prompt forbids rounding, so the model cannot introduce a third rendering. |
| 3 | **Latency stall** | judge scrubs, the panel is blank or spinning | Runtime is a dictionary lookup on a 15 KB static file - there is no request to be slow. The optional live path renders the template first and upgrades in place inside 1200 ms, so nothing ever waits on a response. No spinner survives one heartbeat. |
| 4 | **Network loss** | venue wifi dies mid-demo | Nothing in the demo path touches the network beyond `localhost:8000`. No API key exists in the client. Test it for real: turn wifi off and run the whole demo once on Friday. |
| 5 | **Recommends a pit lap** | "box this lap" / "the window opens on lap 30" - and the deck's headline negative result is now contradicted by our own UI | Prohibition stated with its reason in the prompt (a rule with a reason survives paraphrase). Banned-phrase regex covers the phrasings. The numeric whitelist catches lap numbers that are not the current lap. All checks run before the text is cached. |
| 6 | **Banned vocabulary** | "optimal strategy", "AI-powered" - one word undoes the copy discipline in DEMO_BRIEF section 7 | Explicit never-list in the prompt, mirrored by the regex in section 6. |
| 7 | **Time travel** | at lap 16 the voice says "you box next lap", because `stops[]` contains lap 17 | Filter `stops` to `pit_lap <= L` in the state builder (section 1.3). Add a test: for every lap of R08, assert no field in the block derives from a row with `lap > L`. |
| 8 | **Track temperature narrated as changing** | "track's coming to you now" - it is a race mean and it is the same on every lap | `track_temp_basis` is in the block and the prompt forbids describing the track as changing. |
| 9 | **Empty lap** | scrub to Austria 24 or 25 and the commentary panel is blank, so the feature looks broken | Ladder rung 3: a fixed caption explaining that in-laps, out-laps and non-green laps are filtered. Same panel size, no error styling. Season-wide this matters more than it sounds - Monaco has a twelve-lap hole from 60 to 71, Miami from 5 to 11. The replay scrubber itself needs this caption regardless of whether the LLM feature ships. |
| 10 | **Cache miss on an interactive input** | user drags the gap slider, no cached line exists | The template (5.5) is the default renderer for that surface, not a fallback. It is instant and it is right. |
| 11 | **API key exposed** | key visible in devtools or in the repo on the projector | No key client-side, ever. Pre-generation runs from Python with the key in the environment. Grep the demo folder for `sk-ant` before Saturday. |
| 12 | **Rate limit during pre-generation** | Friday-night build dies at lap 60 | Resumable generator, writes after every lap, skips laps already present. Concurrency 4-8. SDK retries 429/5xx twice by default. |
| 13 | **Stale cache after a model refit** | `model.json` is refit and the cached voice quotes the old numbers while the panel shows the new ones - the one failure on this list that is guaranteed rather than possible | **This has already happened once.** The track-temp causality fix landed on 11 Sep and moved Austria's `MEDIUM>HARD` step from 1.67 to 1.63 s/lap, the first-lap undercut gain from 1.81 to 1.78 s, and the headline RMSE from 0.95 to 0.96 - DEMO_BRIEF's own reference case still quotes the old figures. Mitigation: `prompt_sha256` plus a `model_sha256` of `model.json` in the cache header, checked at load, warning in the console on mismatch. **Regenerating the commentary is a required step after any change to `model.json`**, alongside re-checking the hardcoded numbers in the docs. It is in the section 8 checklist for that reason. |
| 14 | **Model invents a safety car** | "if the safety car comes out..." - we do not fit an SC probability and cannot | Nothing SC-related is in the block, and the prompt confines the model to the flag vocabulary. The `flags` list is closed. |

---

## 8. Checklist

- [ ] `scripts/gen_commentary.py` per section 5.3, with the validator from section 6.
- [ ] `artifacts/demo/commentary/R08.json` generated, 71 laps, zero validation failures.
- [ ] State builder in the UI, with the `stops` filter and the `lap > L` test from failure mode 7.
- [ ] Shared `fmt` used by both the panel and the state block.
- [ ] Four-rung lookup ladder wired, including the caption for laps 24 and 25.
- [ ] Templates rendering on the undercut slider surface.
- [ ] Caption on screen naming the model and stating that it computes nothing.
- [ ] `grep -r "sk-ant" demo/ artifacts/` returns nothing.
- [ ] Full demo rehearsed once with wifi physically off.
- [ ] If `model.json` is refit again: regenerate the commentary, re-run the validator, and
      re-check every hardcoded number in `docs/` before rehearsing. The refit on 11 Sep moved
      Austria's `MEDIUM>HARD` step from 1.67 to 1.63 s/lap and its reference case from `+1.80 s`
      to `+1.76 s`. Both `DEMO_BRIEF.md` section 3 and `DEMO_CONTRACT.md` now carry 1.76, so a
      computed 1.80 means a stale `model.json` rather than a stale doc.
