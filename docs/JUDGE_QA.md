# Judge Q&A — read this the morning of

Aditya and Ruhani. TrackShift 2026, Mohali, Sat 12 Sep. Category: **Tyre Degradation
Intelligence**.

This exists because our project's biggest strength is also its biggest presentational risk. We
cut three features after testing them. To a technical judge that reads as rigour. To a rushed
judge it can read as *"they have less than the other team."* Every answer below is written to
make sure it lands the first way.

**The one sentence to keep in your head:** everyone else will show you a number; we'll show you
which numbers survived contact with the data.

---

## 1. The 90-second pitch

Say it in this order. Do not lead with the model.

> Fit lap time against tyre age on practice data — the obvious thing, what most people do — and
> on the medium and the hard the data says tyres get **faster** as they wear. On the hard it
> claims a seventeen-lap-old tyre is two and a half seconds a lap *quicker* than a fresh one.
> That's not a rounding error, it's the wrong sign.
>
> It happens because the car is burning about a kilogram of fuel a lap while the tyre ages. Fuel
> makes the car quicker, the tyre makes it slower, and inside a single run those two are almost
> perfectly collinear. The fuel effect wins and it drags the sign with it.
>
> So we separated them. We measured fuel sensitivity where fuel and tyre age *aren't* collinear
> — across a race — got **+0.0294 s/kg**, against a literature range of 0.030–0.035, and
> imported it. Every curve flips to the right sign. Then we found we still couldn't transfer a
> practice curve to a race, so we stopped trying and measured the thing a race engineer actually
> decides on instead: **what a fresh tyre is worth, right now, in seconds per lap.** 288 real pit
> stops. The stop is a natural experiment — tyre age resets, fuel doesn't, so the step across it
> is the tyre effect with fuel cancelled.
>
> That number is **+1.26 s/lap** on average, and we predict it to **0.96 s/lap out of sample**,
> leave-one-event-out — the model scoring Silverstone has never seen Silverstone.
>
> And then we tried to build three more things on top of it, tested all three, and cut all
> three. That's the part I actually want to talk about.

Then hand to the demo.

---

## 2. The questions you will definitely get

### "What's your accuracy?"

**0.96 s/lap RMSE, out of sample, leave-one-event-out. Calibration slope 0.79. 11.1% better
than a season-average baseline, across 288 stops and 12 races.**

Then immediately say what it predicts, because this is where people mishear us:

> We don't predict lap times and we don't simulate races. We predict *the step* — how much
> quicker the car is on a fresh tyre than the one it just took off. That's a narrower claim than
> "we predict the race" and it's the reason we can put an honest error bar on it.

Never say "95% accurate." It isn't a percentage and someone will ask 95% of what.

### "Why don't you recommend when to pit? That's the whole problem, isn't it."

This is the question that wins or loses the round. Answer it head-on and with the number.

> We built it. It covers 68.4% of the stops teams actually made. Then we tested it against a
> window of the same width just placed halfway through the race — that scores 65.8%. A 2.6-point
> edge is too small to lean on, so it isn't the test we decided on.
>
> The tighter test is worse: per event, does our window *move* with the lap teams chose? The
> mid-race constant tracks it better than we do — r=+0.73 against +0.64. Divide race length out
> and our signal is r=+0.08, p=0.80. There's nothing there. The coverage was race-length
> arithmetic wearing a strategy costume.
>
> So it's a diagnostic in the codebase and it's not in the product. If we'd shipped it you'd
> have asked me how we validated it, and I'd have had to tell you this anyway.

If pushed on *why* it can't work: the compound change, not the wear, is most of the +1.26 s.
And the compound benefit doesn't depend on *when* you take it, so neither edge of the window
comes from tyre physics — the early edge is stint feasibility, the late edge is laps-left-to-
repay, and both are just arithmetic on race length.

If pushed the other way — *"2.6 points is still better, why not ship it?"* — that's the sharp
version of the question and it deserves a real answer, not a shrug:

> Because I can't tell you what it's better *at*. Coverage rises whenever you widen a window,
> so a window that covered everything would score 100% and know nothing — it's not a measure of
> skill. Underneath those 2.6 points there's no per-event tracking at all, which is what you'd
> expect from a window that happens to sit in a slightly luckier place on this one season. For
> me to ship it, it has to beat the constant on the test a constant is built to fail. It loses
> that one.

### "Does your undercut calculator tell me if I'll gain a place?"

**No, and say so plainly.** We tested this last night and it failed.

> We scored it against 137 real head-to-head duels — a car pits, the car ahead responds later,
> who's ahead afterwards. Cars we flagged won 34% of the time, cars we called against won 5%.
> Looks great.
>
> Then we raced it against the gap alone, no model at all. AUC 0.836. Ours: 0.836. Identical.
> Our model's own contribution, scored by itself, is 0.490 — a coin flip.
>
> It's arithmetic, not a bug. The margin is gain minus gap. The gain we supply varies by about
> half a second across those duels; the gap varies by fifteen. A term thirty times smaller can't
> reorder anything.
>
> So the tool gives you the rate and does the subtraction on screen. It does not tell you you'll
> gain a place, because on this evidence we'd just be telling you what your own stopwatch says.

### "Where's the machine learning?"

Do not get defensive and do not reach for buzzwords. This is a strong answer:

> Regression with compound-pair fixed effects and cluster-robust standard errors. We chose the
> model class for identification, not for flexibility — and that's the point. Put a gradient
> booster on the same confounded features and it reproduces the same sign error with more
> confidence, because nothing in the fitting procedure knows that fuel and tyre age are
> collinear. The hard part here was never the fit. It was working out which comparison is valid.

If they want to see complexity: the two-stage estimation (λ identified from race data, imported
into practice fits) and the pit stop as a natural experiment are both more interesting than a
model choice.

### "Only one season? Only 12 races?"

> 12 races, 12 circuits, 288 stops, all of 2026 so far. It's enough for the claim we make and
> we're explicit about where it isn't. The thing we'd buy with more seasons is compound-specific
> wear rates — that's exactly the quantity we said we couldn't identify, because with three
> compounds over 288 stops the old tyre's compound is nearly determined by where the stint sits
> in the race, so the interaction is collinear with stint position.

### "How do I know the deconfounding actually worked?"

> The pit stop is the check. Tyre age resets to zero across it; fuel load doesn't change. So the
> step in lap time across a stop measures the tyre effect with fuel already cancelled — we don't
> have to trust our fuel correction for that number, it's cancelled by construction. 288 of them,
> mean +1.26 s/lap. That's the anchor everything else is scored against.

### "The soft compound doesn't flip sign though."

Someone sharp will notice this on the chart. It's a good sign if they do — have the number ready.

**Slopes at tyre age 10, s/lap:**

| compound | naive | deconfounded | |
|---|---|---|---|
| SOFT | +0.0518 | +0.1096 | right sign, understated 2.1× |
| MEDIUM | **−0.0459** | +0.0738 | sign flip |
| HARD | **−0.1535** | +0.0631 | sign flip |

> Correct — the soft already has the right sign. It degrades fast enough that the tyre effect
> beats the fuel effect even uncorrected. But it's still understated by a factor of two, so the
> naive fit gets the direction right and the magnitude badly wrong. The harder the compound, the
> weaker the real degradation, and the more completely fuel swamps it — which is exactly the
> pattern you'd predict if the confounder is what we say it is.

That last clause matters: the confound produces an *ordered* error across compounds, not a
random one. That's much harder to explain by chance.

### "What are you not modelling?"

Get in front of this rather than being caught by it.

> Safety cars — 12 races at 12 circuits is one observation per circuit, we can't estimate it, so
> if it appears at all it's a slider you set and we label it your assumption. Weather. Driver
> skill. Track position and traffic beyond a crude proximity term. And track temperature is
> weaker than it looks: 99.9% of its variance is between events, so it's doing the job of
> circuit identity with 12 clusters, not really measuring temperature.

That last one is worth volunteering. If a judge finds it themselves it's a hole; if you say it
first it's evidence you looked.

---

## 3. The awkward ones

### "So you cut three features. What do you actually have?"

> A measured quantity with an honest error bar on it, and three places where we can tell you
> exactly why the obvious next step doesn't work. Everything still standing has been attacked.

### "Isn't this just what F1 teams already do?"

Don't oversell. The honest answer is better.

> Teams have tyre temperatures, pressures, full telemetry and their own tyre models — far more
> than we do. We're working from public timing data. What we're showing isn't a better tyre
> model than Pirelli's; it's that the standard way to read public data gets the *sign* wrong,
> and here's a correction that's testable and tested.

### Something we genuinely don't know

Say so, in one sentence, and offer the nearest thing we do know. Do not improvise a number.
Getting caught inventing one costs more than any answer is worth — and it would undo the entire
point of the presentation.

---

## 4. Demo click path

Drive it in this order. Rehearse it twice.

1. **The sign flip, on the HARD compound** — naive line vs deconfounded. Show HARD first: the
   naive line dives to −2.47 s/lap by age 17 and never comes back. This is the strongest visual
   we have and any judge understands it in ten seconds. *"That line says a seventeen-lap-old
   tyre is two and a half seconds a lap quicker than a fresh one."*
2. **The rate**, live: pick a race, a compound pair, a tyre age. Watch the number move.
3. **The undercut arithmetic** — rate × laps against the gap. Say the pit loss cancels; it's
   counter-intuitive and it's the mechanism.
4. **Race replay**, Austria. Scrub. Numbers move with tyre age.
5. **Validation scatter** — measured against predicted, out of sample. *"Every point is a real
   stop the model had never seen."*

**Failure drills.** Wifi is dead: everything is static JSON, so nothing needs the network — but
check this by turning wifi off and reloading, tonight. Browser won't load: have the scatter and
the sign-flip figure as images in the deck. A number on screen disagrees with the deck: trust
the screen, say the deck is stale, move on — do not debug live.

---

## 5. Three things not to say

- **"Optimal strategy."** We don't have one and we deliberately don't.
- **"AI-powered."** Say what it is. The method is the interesting part.
- **"Our model would have won the race."** Counterfactual race outcomes are not identified from
  this data and we would be inventing them.

---

## 6. If you have five minutes before you go on

Read section 1 and the first three answers in section 2. That's 80% of what gets asked.
