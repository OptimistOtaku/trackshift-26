"""Build the TrackShift 2026 idea-submission deck as a .pptx.

The deck follows the project's evidence chain, not a pitch arc: the naive model gives the wrong
sign -> we deconfound -> the clean curve still fails a race -> so we model the decision directly
-> it survives out of sample. Every number is the one `scripts/stop_value.py` prints, and every
chart is a real artifact.

Run: python scripts/make_deck.py
"""
import os

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
OUT = os.path.join(ART, "PITWALL_TrackShift2026.pptx")

# EDIT ME: replace with your registered team name before uploading.
TEAM = "‹ your team name ›"

# ---- palette ------------------------------------------------------------ #
INK = RGBColor(0x0E, 0x11, 0x16)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
ACCENT = RGBColor(0x0B, 0x6E, 0xA8)
RED = RGBColor(0xD0, 0x02, 0x1B)
WARN = RGBColor(0xC0, 0x39, 0x2B)
GOOD = RGBColor(0x1A, 0x7F, 0x4B)
MUTED = RGBColor(0x8A, 0x8A, 0x8A)
SUBTLE = RGBColor(0x9A, 0xA0, 0xA6)
PANEL = RGBColor(0xF4, 0xF5, 0xF7)
DARKPANEL = RGBColor(0x16, 0x1B, 0x22)
FONT = "Segoe UI"

AR = {}
for f in os.listdir(ART):
    if f.endswith(".png"):
        w, h = Image.open(os.path.join(ART, f)).size
        AR[f] = w / h

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide(bg=PAPER):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s


def box(s, l, t, w, h, anchor=None):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    if anchor is not None:
        tf.vertical_anchor = anchor
    return tf


def para(tf, text, size, color, *, bold=False, italic=False, first=False,
         align=PP_ALIGN.LEFT, after=6, before=0, spacing=1.05, font=FONT):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(after)
    p.space_before = Pt(before)
    p.line_spacing = spacing
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font
    r.font.color.rgb = color
    return p


def bullet(tf, lead, text, size, lead_color, text_color, *, first=False, after=9):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(after)
    p.line_spacing = 1.08
    if lead:
        r1 = p.add_run()
        r1.text = lead + "   "
        r1.font.size = Pt(size)
        r1.font.bold = True
        r1.font.name = FONT
        r1.font.color.rgb = lead_color
    r2 = p.add_run()
    r2.text = text
    r2.font.size = Pt(size)
    r2.font.name = FONT
    r2.font.color.rgb = text_color
    return p


def rect(s, l, t, w, h, fill, line=None):
    sp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1)
    sp.shadow.inherit = False
    return sp


def image_fit(s, name, l, t, w, h):
    ar = AR[name]
    box_ar = w / h
    if ar >= box_ar:
        iw, ih = w, w / ar
    else:
        ih, iw = h, h * ar
    il, it = l + (w - iw) / 2, t + (h - ih) / 2
    s.shapes.add_picture(os.path.join(ART, name), Inches(il), Inches(it),
                         width=Inches(iw), height=Inches(ih))


def header(s, kicker, headline, accent=ACCENT):
    rect(s, 0.55, 0.60, 0.85, 0.07, accent)
    tf = box(s, 0.55, 0.68, 12.2, 0.35)
    para(tf, kicker.upper(), 12.5, accent, bold=True, first=True, after=0)
    tf2 = box(s, 0.5, 0.98, 12.4, 1.0)
    para(tf2, headline, 29, INK, bold=True, first=True, after=0, spacing=1.0)


def footer(s, n, dark=False):
    c = SUBTLE if dark else MUTED
    tf = box(s, 0.55, 7.06, 9, 0.34)
    para(tf, "PITWALL  ·  TrackShift 2026", 9, c, first=True, after=0)
    tf2 = box(s, 12.0, 7.06, 0.85, 0.34)
    para(tf2, str(n), 9, c, first=True, after=0, align=PP_ALIGN.RIGHT)


# ======================================================================== #
# 1. TITLE
# ======================================================================== #
s = slide(INK)
rect(s, 0, 0, 0.28, 7.5, RED)
tf = box(s, 1.15, 1.75, 11, 3.6)
para(tf, "PITWALL", 76, PAPER, bold=True, first=True, after=4, spacing=1.0)
para(tf, "Tyre degradation intelligence from confounded race data", 23, RGBColor(0xD5, 0xDA, 0xDF),
     after=0, spacing=1.05)
rect(s, 1.2, 4.35, 1.5, 0.05, RED)
tf2 = box(s, 1.2, 4.6, 11, 2)
para(tf2, "We built the model everyone builds, proved it gives the wrong answer,",
     15, SUBTLE, first=True, after=1)
para(tf2, "and shipped the one that survives an actual race.", 15, SUBTLE, after=0)
tf3 = box(s, 1.2, 6.35, 11.5, 0.9)
para(tf3, "AI Motorsport Intelligence   ·   Tyre Degradation Intelligence",
     12.5, RGBColor(0xC5, 0xCB, 0xD1), first=True, after=2)
para(tf3, f"Team {TEAM}", 12.5, ACCENT, bold=True, after=0)


# ======================================================================== #
# 2. THE TRAP
# ======================================================================== #
s = slide()
header(s, "The problem", "Everyone fits the same model. It comes out backwards.")
tf = box(s, 0.6, 2.05, 7.0, 4.7)
bullet(tf, "▪", "The brief asks us to isolate true tyre wear from fuel weight, "
        "traffic and track evolution.", 16, ACCENT, INK, first=True, after=11)
bullet(tf, "▪", "The default approach fits lap time against tyre age and calls the "
        "slope “degradation.”", 16, ACCENT, INK, after=11)
bullet(tf, "▪", "On the full 2026 season that slope reports two of three compounds "
        "getting FASTER as they wear.", 16, WARN, INK, after=11)
bullet(tf, "▪", "That is not a bias to note in a limitations section — it is a "
        "wrong answer to the exact question asked.", 16, ACCENT, INK, after=0)
# right callout
rect(s, 8.1, 2.15, 4.55, 3.0, PANEL)
rect(s, 8.1, 2.15, 0.12, 3.0, WARN)
tf2 = box(s, 8.5, 2.45, 4.0, 2.5, anchor=MSO_ANCHOR.MIDDLE)
para(tf2, "naive HARD-tyre “degradation”", 13, MUTED, first=True, after=6)
para(tf2, "−0.15 s/lap", 34, WARN, bold=True, after=6)
para(tf2, "the model claims a 30-lap-old tyre is over a second faster than a fresh one.",
     12.5, INK, after=0, spacing=1.1)
footer(s, 2)


# ======================================================================== #
# 3. THE SIGN ERROR  (fig1)
# ======================================================================== #
s = slide()
header(s, "Why it fails", "Inside a run, fuel burns at exactly the rate tyres age")
tf = box(s, 0.6, 2.15, 5.4, 4.6)
bullet(tf, "1", "Fuel makes the car faster as the run goes on; tyres make it slower. Within a "
        "single run the two are perfectly collinear.", 15, ACCENT, INK, first=True, after=10)
bullet(tf, "2", "The naive slope measures their difference — not wear.", 15, ACCENT, INK,
       after=10)
bullet(tf, "3", "Correcting fuel, then traffic, then track evolution flips every compound "
        "to a physically sensible positive number.", 15, ACCENT, INK, after=10)
bullet(tf, "→", "Deconfounding is not cosmetic here. It changes the sign of the answer, "
        "and therefore the pit-stop call.", 15, GOOD, INK, after=0)
image_fit(s, "fig1_ladder.png", 6.2, 2.0, 6.75, 4.7)
footer(s, 3)


# ======================================================================== #
# 4. IDENTIFICATION  (fig2)
# ======================================================================== #
s = slide()
header(s, "Identification", "Three levers make the tyre effect recoverable")
tf = box(s, 0.6, 2.1, 5.5, 4.7)
bullet(tf, "Fuel", "— from the race, where fuel falls monotonically while tyre age "
        "saw-tooths at every stop. λ = +0.029 s/kg, matching the literature 0.030–0.035.",
        14.5, ACCENT, INK, first=True, after=12)
bullet(tf, "Evolution", "— as log1p(weekend laps). Its within-run slope varies ~11× "
        "from FP1 to FP3 while tyre age is always 1/lap, so the log saturates and is not "
        "collinear with age.", 14.5, ACCENT, INK, after=12)
bullet(tf, "Traffic", "— measured from car position telemetry: a KD-tree snap to the "
        "racing line gives the time gap to the car ahead. Measured, never guessed.", 14.5,
        ACCENT, INK, after=0)
image_fit(s, "fig2_identification.png", 6.3, 2.05, 6.6, 4.6)
footer(s, 4)


# ======================================================================== #
# 5. THE HONEST TEST  (fig4)
# ======================================================================== #
s = slide()
header(s, "The test most teams skip", "A clean in-sample curve that does not survive a race",
       accent=WARN)
tf = box(s, 0.6, 2.15, 5.4, 4.6)
bullet(tf, "▪", "We could have stopped at the deconfounded curve. Instead we asked "
        "whether it predicts a real race.", 15, WARN, INK, first=True, after=11)
bullet(tf, "▪", "Prediction target: the pace gained across 288 actual pit stops.", 15,
       WARN, INK, after=11)
bullet(tf, "▪", "It is right on average — +1.52 s predicted vs +1.26 s observed "
        "— and its stop-by-stop variation is uncorrelated with truth.", 15, WARN, INK,
       after=11)
bullet(tf, "▪", "Calibration slope 0.006. A saturating form does not rescue it: the "
        "timescale τ is unidentified.", 15, WARN, INK, after=0)
image_fit(s, "fig4_transfer_failure.png", 6.7, 1.95, 6.2, 4.85)
footer(s, 5)


# ======================================================================== #
# 6. THE PIVOT
# ======================================================================== #
s = slide()
header(s, "The pivot", "Model the decision, not the curve")
tf = box(s, 0.6, 2.15, 7.1, 4.6)
bullet(tf, "▪", "The pit stop is a natural experiment: across it, tyre age resets to "
        "zero but fuel barely moves.", 16, ACCENT, INK, first=True, after=12)
bullet(tf, "▪", "So the step in pace across a stop measures the tyre effect with fuel "
        "almost entirely cancelled — no model assumption required.", 16, ACCENT, INK,
       after=12)
bullet(tf, "▪", "We model the quantity an engineer actually decides on: the seconds per "
        "lap a fresh tyre buys. Learned from race history, not a practice fit.", 16, ACCENT,
       INK, after=0)
rect(s, 8.35, 2.35, 4.35, 2.7, INK)
tf2 = box(s, 8.6, 2.65, 3.9, 2.2, anchor=MSO_ANCHOR.MIDDLE)
para(tf2, "a fresh tyre is worth", 14, SUBTLE, first=True, after=4)
para(tf2, "+1.26 s/lap", 40, PAPER, bold=True, after=4)
para(tf2, "288 stops · 12 events · sd 1.03", 12.5, SUBTLE, after=0)
footer(s, 6)


# ======================================================================== #
# 7. THE FINDING  (fig3)
# ======================================================================== #
s = slide()
header(s, "The finding", "Degradation accumulates for ~20 laps — then stops")
tf = box(s, 0.6, 2.15, 5.4, 4.6)
bullet(tf, "▪", "A linear test on tyre age finds nothing (p = 0.58). That is the trap, "
        "not the answer.", 15, WARN, INK, first=True, after=11)
bullet(tf, "▪", "With curvature, age and age² are jointly significant (p = 0.005) "
        "and the value of a stop peaks near tyre age 21, then declines.", 15, ACCENT, INK,
       after=11)
bullet(tf, "▪", "It is an inverted U. A straight line averages it to zero and reports a "
        "confident, wrong null.", 15, ACCENT, INK, after=11)
bullet(tf, "→", "Consequence: a curve that keeps climbing over-values a late stop — "
        "a systematic bias toward stopping too often.", 15, GOOD, INK, after=0)
image_fit(s, "fig3_age_null.png", 6.3, 2.05, 6.6, 4.6)
footer(s, 7)


# ======================================================================== #
# 8. RESULTS  (fig6)
# ======================================================================== #
s = slide()
header(s, "Results", "Beats the baseline out of sample, event by event", accent=GOOD)
tf = box(s, 0.6, 2.1, 5.4, 4.7)
bullet(tf, "▪", "Leave-one-event-out, with no free constant granted to any method — "
        "the model must get the level right, not just the shape.", 14.5, GOOD, INK, first=True,
       after=10)
bullet(tf, "+11.9%", "RMSE over the season-mean baseline; calibration slope 0.82; wins 7 of "
        "11 held-out events.", 14.5, GOOD, INK, after=10)
bullet(tf, "▪", "Robust to method-blind outlier caps (+10–12% across all cuts).",
       14.5, GOOD, INK, after=10)
bullet(tf, "▪", "Signal: compound pair, track temp (+0.041 s/°C, p<0.001) and "
        "traffic (+0.50 s, p=0.003). Tyre age is reported but not deployed — it costs "
        "accuracy out of sample.", 14.5, GOOD, INK, after=0)
image_fit(s, "fig6_per_event.png", 6.3, 2.1, 6.6, 4.55)
footer(s, 8)


# ======================================================================== #
# 9. VALIDATION RIGOUR
# ======================================================================== #
s = slide()
header(s, "Why trust it", "Validated against a natural experiment, not its own fit")
tf = box(s, 0.6, 2.1, 6.0, 4.7)
bullet(tf, "▪", "Ground truth is the pit-stop step, where fuel cancels — not an "
        "in-sample R² the model can inflate on its own.", 15, ACCENT, INK, first=True,
       after=11)
bullet(tf, "▪", "Leave-one-event-out cross-validation; no method receives a free "
        "constant.", 15, ACCENT, INK, after=11)
bullet(tf, "▪", "Cluster-robust standard errors — by run for lap fits, by event for "
        "stop fits.", 15, ACCENT, INK, after=11)
bullet(tf, "▪", "Falsification: the traffic measure rises monotonically from P1–3 to "
        "P16–20, exactly as it must.", 15, ACCENT, INK, after=11)
bullet(tf, "▪", "Limits stated, not smoothed: the pooled gain is carried by larger "
        "events; track temp partly proxies circuit identity over only 12 events.", 15, MUTED,
       INK, after=0)
rect(s, 7.05, 2.15, 5.6, 4.5, PANEL)
tf2 = box(s, 7.4, 2.5, 4.95, 3.9, anchor=MSO_ANCHOR.MIDDLE)
para(tf2, "OUT-OF-SAMPLE SCORECARD", 12, ACCENT, bold=True, first=True, after=12)
for k, v in (("RMSE gain vs season mean", "+11.9%"), ("calibration slope", "0.82"),
             ("events won", "7 / 11"), ("stops scored", "288"),
             ("fuel λ vs literature", "0.029 / 0.030–0.035")):
    p = tf2.add_paragraph()
    p.space_after = Pt(10)
    r1 = p.add_run(); r1.text = k + "    "
    r1.font.size = Pt(14); r1.font.name = FONT; r1.font.color.rgb = INK
    r2 = p.add_run(); r2.text = v
    r2.font.size = Pt(14); r2.font.bold = True; r2.font.name = FONT; r2.font.color.rgb = GOOD
footer(s, 9)


# ======================================================================== #
# 10. REAL-WORLD TRANSFER
# ======================================================================== #
s = slide()
header(s, "Beyond motorsport", "The same trap sits in Indian fleet tyre management")
tf = box(s, 0.6, 2.1, 7.1, 4.7)
bullet(tf, "▪", "The transferable method: recover a wear signal from confounded "
        "operating conditions, then validate on a natural experiment — never in sample.",
        15.5, ACCENT, INK, first=True, after=12)
bullet(tf, "▪", "Target: Indian commercial-vehicle fleets. Wear is confounded by axle "
        "load, road roughness, ambient temperature and driver behaviour — structurally "
        "the identical problem.", 15.5, ACCENT, INK, after=12)
bullet(tf, "▪", "Tyre cost is a top controllable line item in Indian trucking, and tyre "
        "burst is a recognised cause of highway fatalities.", 15.5, ACCENT, INK, after=12)
bullet(tf, "→", "The warning transfers too: an in-sample wear curve can look excellent "
        "and carry almost no predictive value. Only a natural experiment reveals which you "
        "have.", 15.5, GOOD, INK, after=0)
rect(s, 8.05, 2.2, 4.6, 3.15, INK)
tf2 = box(s, 8.35, 2.5, 4.05, 2.6, anchor=MSO_ANCHOR.MIDDLE)
para(tf2, "SAME MATH, NEW CONFOUNDERS", 11.5, SUBTLE, bold=True, first=True, after=10)
para(tf2, "fuel → axle load", 15, PAPER, after=5)
para(tf2, "traffic → road roughness", 15, PAPER, after=5)
para(tf2, "track evo → ambient temp", 15, PAPER, after=5)
para(tf2, "pit stop → tyre swap record", 15, PAPER, after=0)
footer(s, 10)


# ======================================================================== #
# 11. TECH & DATA
# ======================================================================== #
s = slide()
header(s, "Stack", "Built on real telemetry, reproducible end to end")
col1 = box(s, 0.6, 2.15, 4.0, 4.6)
para(col1, "DATA", 13, ACCENT, bold=True, first=True, after=8)
para(col1, "FastF1 — full 2026 F1 season", 14.5, INK, bold=True, after=3)
para(col1, "14,310 laps · 12 events · 1,068 runs", 13.5, MUTED, after=6)
para(col1, "Per-lap timing, tyre compound and age, plus 4–10 Hz car position telemetry.",
     13.5, INK, after=0, spacing=1.12)
col2 = box(s, 4.85, 2.15, 4.0, 4.6)
para(col2, "METHODS", 13, ACCENT, bold=True, first=True, after=8)
for t in ("Two-stage hierarchical fuel + degradation model",
          "Frisch–Waugh–Lovell demeaning absorbs ~1,100 run fixed effects",
          "Cluster-robust standard errors",
          "KD-tree racing-line traffic measurement",
          "Profile likelihood over the saturating form"):
    bullet(col2, "•", t, 13.5, ACCENT, INK, after=8)
col3 = box(s, 9.1, 2.15, 3.7, 4.6)
para(col3, "TOOLS", 13, ACCENT, bold=True, first=True, after=8)
para(col3, "Python", 14.5, INK, bold=True, after=3)
para(col3, "pandas · NumPy · statsmodels · SciPy · matplotlib", 13.5, INK,
     after=10, spacing=1.15)
para(col3, "REPRODUCIBILITY", 13, ACCENT, bold=True, after=8)
para(col3, "One script regenerates every number and figure from the cached season.", 13.5,
     INK, after=0, spacing=1.15)
footer(s, 11)


# ======================================================================== #
# 12. CLOSE
# ======================================================================== #
s = slide(INK)
rect(s, 0, 0, 0.28, 7.5, RED)
tf = box(s, 1.15, 1.5, 11.5, 2.2)
para(tf, "PITWALL", 54, PAPER, bold=True, first=True, after=6)
para(tf, "We built the model everyone builds, proved it gives the wrong answer,",
     19, RGBColor(0xD5, 0xDA, 0xDF), after=1)
para(tf, "and shipped the one that survives an actual race.", 19, RGBColor(0xD5, 0xDA, 0xDF),
     after=0)
tiles = [("+0.029 s/kg", "fuel sensitivity, matches the literature", ACCENT),
         ("0.006", "calibration of the curve everyone ships", WARN),
         ("+11.9%", "out-of-sample gain of the model we ship", GOOD)]
for i, (big, small, col) in enumerate(tiles):
    x = 1.2 + i * 3.9
    rect(s, x, 4.15, 3.55, 1.85, DARKPANEL)
    rect(s, x, 4.15, 3.55, 0.09, col)
    t = box(s, x + 0.28, 4.4, 3.0, 1.5, anchor=MSO_ANCHOR.MIDDLE)
    para(t, big, 30, PAPER, bold=True, first=True, after=4)
    para(t, small, 12, SUBTLE, after=0, spacing=1.05)
tf3 = box(s, 1.2, 6.5, 11, 0.6)
para(tf3, f"Team {TEAM}   ·   AI Motorsport Intelligence   ·   TrackShift 2026",
     13, SUBTLE, first=True, after=0)

prs.save(OUT)
print("wrote", OUT, "—", len(prs.slides._sldIdLst), "slides")
