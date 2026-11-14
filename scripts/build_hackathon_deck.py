"""
Generate the official TrackShift 2026 Hackathon Presentation Deck for PITWALL.
Team: Handsome Squidward
Members: Aditya and Ruhani
Project: PITWALL - Opponent-Aware Tyre Strategy Intelligence
"""
import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
SUBMISSION = os.path.join(ART, "submission")
os.makedirs(SUBMISSION, exist_ok=True)

OUT_FINAL = os.path.join(SUBMISSION, "PITWALL_Handsome_Squidward_Final.pptx")
OUT_UPDATED = os.path.join(SUBMISSION, "PITWALL_Handsome_Squidward_Updated.pptx")

# ---- PALETTE & TYPOGRAPHY -------------------------------------------------- #
BG_DARK = RGBColor(0x0A, 0x0E, 0x0D)        # #0A0E0D - Formula 1 stealth black
CARD_BG = RGBColor(0x13, 0x1A, 0x16)        # #131A16 - dark elevated surface
CARD_BORDER = RGBColor(0x23, 0x2E, 0x27)    # #232E27 - subtle border
LIME = RGBColor(0xE6, 0xFC, 0x74)           # #E6FC74 - electric pitwall lime
ORANGE = RGBColor(0xE4, 0xA0, 0x6D)         # #E4A06D - race strategy orange / warning
WHITE = RGBColor(0xED, 0xF0, 0xED)          # #EDF0ED - crisp readable text
DIM = RGBColor(0xA6, 0xB0, 0xA7)            # #A6B0A7 - muted secondary text
MUTED = RGBColor(0x64, 0x70, 0x66)          # #647066 - tertiary label text
SOFT_RED = RGBColor(0xE1, 0x06, 0x00)       # Pirelli Soft compound red
MED_YELLOW = RGBColor(0xFF, 0xD7, 0x00)     # Pirelli Medium compound yellow
HARD_WHITE = RGBColor(0xFF, 0xFF, 0xFF)     # Pirelli Hard compound white

FONT_HEAD = "Segoe UI"
FONT_BODY = "Segoe UI"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK_LAYOUT = prs.slide_layouts[6]

def create_slide(bg=BG_DARK, notes=""):
    s = prs.slides.add_slide(BLANK_LAYOUT)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    if notes and s.notes_slide:
        s.notes_slide.notes_text_frame.text = notes
    return s

def add_header(s, kicker, title, top_in=0.45):
    # Kicker
    tb_k = s.shapes.add_textbox(Inches(0.8), Inches(top_in), Inches(11.7), Inches(0.35))
    tf_k = tb_k.text_frame
    tf_k.word_wrap = True
    tf_k.margin_left = tf_k.margin_top = tf_k.margin_right = tf_k.margin_bottom = 0
    p_k = tf_k.paragraphs[0]
    p_k.text = kicker.upper()
    p_k.font.name = FONT_HEAD
    p_k.font.size = Pt(11)
    p_k.font.bold = True
    p_k.font.color.rgb = LIME

    # Title
    tb_t = s.shapes.add_textbox(Inches(0.8), Inches(top_in + 0.35), Inches(11.7), Inches(0.65))
    tf_t = tb_t.text_frame
    tf_t.word_wrap = True
    tf_t.margin_left = tf_t.margin_top = tf_t.margin_right = tf_t.margin_bottom = 0
    p_t = tf_t.paragraphs[0]
    p_t.text = title
    p_t.font.name = FONT_HEAD
    p_t.font.size = Pt(26)
    p_t.font.bold = True
    p_t.font.color.rgb = WHITE

def add_card(s, left, top, width, height, bg=CARD_BG, border=CARD_BORDER):
    shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg
    shape.line.color.rgb = border
    shape.line.width = Pt(1)
    return shape

def add_para(tf, text, size=14, color=WHITE, bold=False, italic=False, align=PP_ALIGN.LEFT, space_after=6):
    p = tf.add_paragraph() if len(tf.paragraphs[0].text) > 0 else tf.paragraphs[0]
    p.alignment = align
    p.space_after = Pt(space_after)
    r = p.add_run()
    r.text = text
    r.font.name = FONT_BODY
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    return p

# ============================================================================ #
# SLIDE 1: TITLE SLIDE
# ============================================================================ #
s1_notes = (
    "Good morning judges and motorsport fans. We are team Handsome Squidward, comprising Aditya and Ruhani. "
    "Today we are presenting PITWALL: Opponent-Aware Tyre Strategy & Degradation Intelligence. "
    "Formula 1 race strategies are won and lost on fractional seconds, but lap times are deceptive. "
    "PITWALL isolates pure tyre performance from confounders like fuel and traffic, then provides real-time "
    "attack pricing for the race engineer."
)
s1 = create_slide(notes=s1_notes)

# Top badge
badge = add_card(s1, 0.8, 0.8, 4.2, 0.4, bg=CARD_BG, border=LIME)
tf_b = badge.text_frame
tf_b.vertical_anchor = MSO_ANCHOR.MIDDLE
add_para(tf_b, "TRACKSHIFT 2026  /  AI MOTORSPORT TRACK", size=10, color=LIME, bold=True, align=PP_ALIGN.CENTER, space_after=0)

# Hero Title
tb1 = s1.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.7), Inches(2.2))
tf1 = tb1.text_frame
tf1.word_wrap = True
tf1.margin_left = tf1.margin_top = 0
add_para(tf1, "PITWALL", size=76, color=LIME, bold=True, space_after=4)
add_para(tf1, "Opponent-Aware Tyre Strategy & Degradation Intelligence", size=26, color=WHITE, bold=True, space_after=8)
add_para(tf1, "Separating true tyre degradation from fuel, traffic & track evolution — then pricing the pit attack.", size=16, color=DIM, space_after=0)

# 3 Highlights Cards
cards_data = [
    ("PROBLEM SOLVED", "Lap times are not tyre wear sensors. Naive models claim tyres get faster. We deconfound fuel, traffic & rubbering."),
    ("LIVE STRATEGY ENGINE", "One Driver Clock with 4-stage decision flow: Tyre Condition -> Forecast Pace -> Plan Stop -> Rejoin & Attack."),
    ("PROVEN ACCURACY", "12.0% lower pace RMSE (0.743s) & 10.0% rival RMSE reduction across 6,831 scored chronological forecasts.")
]
for i, (head, desc) in enumerate(cards_data):
    c = add_card(s1, 0.8 + i * 3.95, 4.2, 3.75, 1.8)
    tf_c = c.text_frame
    tf_c.margin_left = tf_c.margin_right = Inches(0.2)
    tf_c.margin_top = Inches(0.2)
    add_para(tf_c, head, size=12, color=LIME, bold=True, space_after=6)
    add_para(tf_c, desc, size=13, color=WHITE, space_after=0)

# Footer bar
foot1 = add_card(s1, 0.8, 6.35, 11.733, 0.65, bg=CARD_BG, border=CARD_BORDER)
tf_f1 = foot1.text_frame
tf_f1.vertical_anchor = MSO_ANCHOR.MIDDLE
tf_f1.margin_left = Inches(0.25)
add_para(tf_f1, "TEAM: HANDSOME SQUIDWARD   |   MEMBERS: ADITYA & RUHANI   |   FASTF1 2026 ARCHITECTURE", size=12, color=DIM, bold=True, space_after=0)


# ============================================================================ #
# SLIDE 2: THE PROBLEM STATEMENT - COLLINEARITY TRAP
# ============================================================================ #
s2_notes = (
    "Why do traditional tyre degradation models fail? In Formula 1, fuel burns at ~0.03 s/kg. "
    "Within a single practice run, fuel burn is perfectly collinear with tyre age. "
    "A standard naive regression actually reports HARD tyres getting FASTER (-0.154 s per lap) because fuel burn masks wear. "
    "When we deconfound fuel, traffic, and track rubbering, the slope restores to +0.063 s/lap. "
    "Crucially, we also discovered that even a clean practice curve fails when applied out-of-sample to race pit stops (calibration slope +0.006)."
)
s2 = create_slide(notes=s2_notes)
add_header(s2, "01 / THE CORE PROBLEM", "Lap Time Is Not a Tyre Wear Measurement")

# Left Column: The Trap
c_s2_left = add_card(s2, 0.8, 1.6, 5.7, 5.2)
tf_s2_l = c_s2_left.text_frame
tf_s2_l.margin_left = tf_s2_l.margin_right = Inches(0.3)
tf_s2_l.margin_top = Inches(0.3)

add_para(tf_s2_l, "THE COLLINEARITY ILLUSION", size=16, color=ORANGE, bold=True, space_after=8)
add_para(tf_s2_l, "Inside a single practice or race stint, fuel burns off monotonically as tyre age increases. Because fuel loss makes the car lighter and faster, naive OLS regression yields an unphysical sign error:", size=13, color=WHITE, space_after=12)

# Comparison stat boxes inside left card
add_para(tf_s2_l, "NAIVE HARD TYRE FIT (UNPHYSICAL)", size=11, color=MUTED, bold=True, space_after=2)
add_para(tf_s2_l, "−0.154 s / lap  (Claims tyres get faster!)", size=18, color=ORANGE, bold=True, space_after=14)

add_para(tf_s2_l, "DECONFOUNDED PITWALL FIT (PHYSICAL)", size=11, color=MUTED, bold=True, space_after=2)
add_para(tf_s2_l, "+0.063 s / lap  (Correct positive wear rate)", size=18, color=LIME, bold=True, space_after=16)

add_para(tf_s2_l, "KEY CONPOUNDERS ISOLATED:", size=12, color=WHITE, bold=True, space_after=4)
add_para(tf_s2_l, "• Fuel Mass Burn: 0.0294 s/kg estimated directly from race refuel resets.\n• Track Evolution: Logarithmic rubbering saturation across sessions.\n• Traffic & Dirty Air: Measured distance gaps to cars ahead.", size=12, color=DIM, space_after=0)

# Right Column: Embedded Fig1 Ladder
c_s2_right = add_card(s2, 6.8, 1.6, 5.7, 5.2)
tf_s2_r = c_s2_right.text_frame
tf_s2_r.margin_left = tf_s2_r.margin_right = Inches(0.3)
tf_s2_r.margin_top = Inches(0.25)
add_para(tf_s2_r, "EMPIRICAL PROOF: THE SPECIFICATION LADDER", size=16, color=LIME, bold=True, space_after=6)
add_para(tf_s2_r, "Step-by-step deconfounding restores positive physical degradation slopes across SOFT, MEDIUM, and HARD compounds:", size=12, color=DIM, space_after=8)

# Embed fig1_ladder.png
fig1_path = os.path.join(ART, "fig1_ladder.png")
if os.path.exists(fig1_path):
    s2.shapes.add_picture(fig1_path, Inches(7.0), Inches(2.7), width=Inches(5.3))


# ============================================================================ #
# SLIDE 3: SCIENTIFIC INNOVATION & RECOVERY PARADOX
# ============================================================================ #
s3_notes = (
    "Here is the pivotal breakthrough of the project: traditional data scientists assume you can take a practice "
    "degradation curve and plug it into a race simulator. We tested that: it fails completely! "
    "The practice curve had a calibration slope of +0.006 when predicting real race pit stop transitions. "
    "Why? Because tyre degradation accumulates for roughly 20 laps and then plateaus. "
    "Instead of trying to force an unobservable wear percentage, PITWALL models the observable quantity a race engineer needs: "
    "the actual lap time recovered across a pit stop (+1.26s/lap fresh tyre value)."
)
s3 = create_slide(notes=s3_notes)
add_header(s3, "02 / SCIENTIFIC BREAKTHROUGH", "The Practice-to-Race Transfer Failure & Observable Recovery")

# Left Column: Fig4 Transfer Failure
c_s3_l = add_card(s3, 0.8, 1.6, 5.7, 5.2)
tf_s3_l = c_s3_l.text_frame
tf_s3_l.margin_left = tf_s3_l.margin_right = Inches(0.3)
tf_s3_l.margin_top = Inches(0.25)
add_para(tf_s3_l, "THE TRANSFER FAILURE EVIDENCE", size=16, color=ORANGE, bold=True, space_after=4)
add_para(tf_s3_l, "Practice curves get season averages roughly right (+1.52s pred vs +1.26s actual) but fail stop-by-stop variation entirely (slope +0.006):", size=12, color=DIM, space_after=6)

fig4_path = os.path.join(ART, "fig4_transfer_failure.png")
if os.path.exists(fig4_path):
    s3.shapes.add_picture(fig4_path, Inches(1.3), Inches(2.7), width=Inches(4.7))

# Right Column: The Solution - Observable Decision Modeling
c_s3_r = add_card(s3, 6.8, 1.6, 5.7, 5.2)
tf_s3_r = c_s3_r.text_frame
tf_s3_r.margin_left = tf_s3_r.margin_right = Inches(0.3)
tf_s3_r.margin_top = Inches(0.3)
add_para(tf_s3_r, "THE PITWALL SOLUTION: OBSERVABLE DELTAS", size=16, color=LIME, bold=True, space_after=8)
add_para(tf_s3_r, "Rather than predicting unobservable physical wear, PITWALL models what engineers actually need: ground truth pace gains across tyre resets.", size=13, color=WHITE, space_after=14)

add_para(tf_s3_r, "1. PIT STOPS AS NATURAL EXPERIMENTS", size=13, color=LIME, bold=True, space_after=3)
add_para(tf_s3_r, "At a pit stop, tyre age abruptly resets to zero while fuel mass remains continuous. The pace step directly isolates the fresh rubber effect.", size=12, color=DIM, space_after=12)

add_para(tf_s3_r, "2. MEASURED FRESH TYRE VALUE", size=13, color=LIME, bold=True, space_after=3)
add_para(tf_s3_r, "Empirical fresh tyre recovery is +1.26 s/lap (sd 1.03) measured across 288 real Formula 1 stops.", size=12, color=DIM, space_after=12)

add_para(tf_s3_r, "3. REGULARIZED DECISION ENSEMBLE", size=13, color=LIME, bold=True, space_after=3)
add_para(tf_s3_r, "Combines compound pair, saturating age basis, track temperature, observed traffic, and recent pace state. Delivers 11.8% RMSE reduction vs mean.", size=12, color=DIM, space_after=0)


# ============================================================================ #
# SLIDE 4: THE 4-STAGE LIVE DECISION SEQUENCE
# ============================================================================ #
s4_notes = (
    "To make this actionable on the pit wall, we designed the 4-Stage Live Decision Sequence. "
    "This matches the exact workflow seen at the top of our race console: "
    "01 Tyre Condition assesses the current stint age and isolated degradation trend. "
    "02 Forecast Pace projects the driver's pace over the next laps with uncertainty intervals. "
    "03 Plan the Stop evaluates fitting alternative compounds (e.g. fitting Hard) and models pit transit loss. "
    "04 Rejoin & Attack calculates opponent battles, rejoin traffic, and undercut stress test."
)
s4 = create_slide(notes=s4_notes)
add_header(s4, "03 / OPERATIONAL ARCHITECTURE", "The 4-Stage Live Decision Sequence")

seq_data = [
    ("01", "TYRE CONDITION", "SOFT / 16 Laps", "-0.00s / lap trend",
     "Stint age tracking, compound state, and fuel-corrected pace trend. Assesses remaining life without relying on misleading wear sensors."),
    ("02", "FORECAST PACE", "Lap 70 Forecast", "83.16s (70% CI)",
     "Precomputed chronological machine learning model (Ridge + State Space + Gradient Boosting). Locked ahead of time for auditable scoring."),
    ("03", "PLAN THE STOP", "Fit Hard Option", "+1.15s / lap delta",
     "Estimates pace step across pit stop (+1.15s/lap response) against a 22.5s pit loss. Compares Hard vs Medium vs Soft compound availability."),
    ("04", "REJOIN & ATTACK", "Rejoin vs HAM", "+2.2s gap behind",
     "Models projected traffic window (13/22 cars clear). Runs undercut stress test against rival clock, accounting for out-lap tyre warm-up.")
]

for i, (step_num, step_title, badge_val, stat_val, detail) in enumerate(seq_data):
    left_x = 0.8 + i * 2.95
    c_seq = add_card(s4, left_x, 1.6, 2.8, 5.2)
    tf_seq = c_seq.text_frame
    tf_seq.margin_left = tf_seq.margin_right = Inches(0.2)
    tf_seq.margin_top = Inches(0.25)
    
    # Step header badge
    add_para(tf_seq, f"STAGE {step_num}", size=11, color=LIME, bold=True, space_after=2)
    add_para(tf_seq, step_title, size=15, color=WHITE, bold=True, space_after=12)
    
    # Value chip
    add_para(tf_seq, badge_val, size=13, color=ORANGE, bold=True, space_after=2)
    add_para(tf_seq, stat_val, size=16, color=LIME, bold=True, space_after=14)
    
    # Detail description
    add_para(tf_seq, detail, size=12, color=DIM, space_after=0)

# Connecting arrow labels at bottom
foot_seq = add_card(s4, 0.8, 6.35, 11.733, 0.65, bg=CARD_BG, border=CARD_BORDER)
tf_fseq = foot_seq.text_frame
tf_fseq.vertical_anchor = MSO_ANCHOR.MIDDLE
tf_fseq.margin_left = Inches(0.25)
add_para(tf_fseq, "STREAMLINED WORKFLOW: INGEST SENSORS → PROJECT PACE → SIMULATE STOPS → STRESS TEST ATTACK MARGIN", size=11, color=WHITE, bold=True, space_after=0)


# ============================================================================ #
# SLIDE 5: LIVE RACE CONSOLE - FRONTEND SHOWCASE (USER ATTACHMENT REFERENCE)
# ============================================================================ #
s5_notes = (
    "Here is PITWALL in action. This is our live interactive motorsport console, running 100% client-side. "
    "At the center is the reconstructed 4.349 km Hungaroring circuit with real driver spatial coordinates. "
    "On the left, the One Driver Clock projects Norris at 83.16s, with the locked auto-verification box showing "
    "just 0.475s error on Lap 69 against the 83.364s actual. "
    "On the right, the race engineer briefing checks signal integrity (weather 31s old, 100% traffic coverage) "
    "and verifies whether rival undercut scenarios are supported."
)
s5 = create_slide(notes=s5_notes)
add_header(s5, "04 / PRODUCT SHOWCASE", "Interactive Formula 1 Pitwall Console")

# Left side: The attached image
ui_img_path = os.path.join(ART, "frontend_ui_reference.png")
if os.path.exists(ui_img_path):
    # 16:9 image: width 7.4 inches, height 4.16 inches
    s5.shapes.add_picture(ui_img_path, Inches(0.8), Inches(1.6), width=Inches(7.4))

# Caption under the image
cap_box = add_card(s5, 0.8, 5.9, 7.4, 0.9, bg=CARD_BG, border=CARD_BORDER)
tf_cap = cap_box.text_frame
tf_cap.margin_left = Inches(0.2)
tf_cap.margin_top = Inches(0.12)
add_para(tf_cap, "LIVE TELEMETRY REPLAY & SPATIAL TRACK RECONSTRUCTION (HUNGARORING)", size=11, color=LIME, bold=True, space_after=2)
add_para(tf_cap, "Sub-second driver coordinates, gear, speed & throttle synchronization with audited model prediction overlays.", size=11, color=DIM, space_after=0)

# Right Column: Architectural Highlights of the UI
c_s5_r = add_card(s5, 8.4, 1.6, 4.133, 5.2)
tf_s5_r = c_s5_r.text_frame
tf_s5_r.margin_left = tf_s5_r.margin_right = Inches(0.25)
tf_s5_r.margin_top = Inches(0.25)

add_para(tf_s5_r, "KEY CONSOLE INNOVATIONS", size=15, color=LIME, bold=True, space_after=10)

ui_features = [
    ("ONE DRIVER CLOCK", "Unifies position replay with precomputed machine learning predictions. All timing lines align to shared track coordinates."),
    ("AUTO-VERIFIED RECEIPT", "Freezes issued forecast at Lap 25. Only reveals actual lap time when replay crosses the line, guaranteeing honest validation."),
    ("FRESH TYRE STOP RESPONSE", "Dynamically updates tyre delta (+1.15s/lap on HARD) based on stint age and historical stop responses."),
    ("SIGNAL INTEGRITY AUDIT", "Reports sensor latency (weather feed 31s old, 100% traffic coverage). Transparently warns that carcass temp & wear are omitted.")
]

for title_f, desc_f in ui_features:
    add_para(tf_s5_r, title_f, size=12, color=ORANGE, bold=True, space_after=2)
    add_para(tf_s5_r, desc_f, size=11, color=WHITE, space_after=10)


# ============================================================================ #
# SLIDE 6: STRATEGY LAB - UNDERCUT STRESS TESTING
# ============================================================================ #
s6_notes = (
    "How does PITWALL help make better strategy decisions? Consider the classic undercut. "
    "Traditional tools say: 'You have a 1.67s advantage, box now!' "
    "PITWALL prices the attack with an explicit waterfall budget: "
    "3 laps of fresh tyre benefit (+3.95s), minus rival pace (-0.08s), minus track gap (-1.50s), minus out-lap warm-up (-0.70s). "
    "That leaves a central margin of +1.67s. "
    "However, we stress-test this against traffic: adding just 2 seconds of traffic delay turns it into -0.33s. "
    "Because the uncertainty interval spans from -8.9s to +8.2s, the engineer knows this is high-risk."
)
s6 = create_slide(notes=s6_notes)
add_header(s6, "05 / STRATEGY EDGE", "Pricing the Undercut: Attack Budgeting Under Uncertainty")

# Left Column: The Undercut Waterfall
c_s6_l = add_card(s6, 0.8, 1.6, 5.7, 5.2)
tf_s6_l = c_s6_l.text_frame
tf_s6_l.margin_left = tf_s6_l.margin_right = Inches(0.3)
tf_s6_l.margin_top = Inches(0.25)

add_para(tf_s6_l, "THE ATTACK BUDGET WATERFALL", size=16, color=LIME, bold=True, space_after=6)
add_para(tf_s6_l, "An undercut is not an abstract win probability; it is a concrete seconds budget that must absorb real-world execution costs:", size=12, color=DIM, space_after=12)

waterfall_items = [
    ("Fresh Tyre Advantage (3 laps)", "+3.95 s", LIME),
    ("Rival In-Lap Pace Response", "−0.08 s", ORANGE),
    ("Current Track Interval to Cover", "−1.50 s", ORANGE),
    ("Cold Out-Lap Warm-Up Penalty", "−0.70 s", ORANGE),
    ("NET ATTACK MARGIN (CLEAN AIR)", "+1.67 s", LIME),
    ("ADD 2.0s REJOIN TRAFFIC DELAY", "−0.33 s", ORANGE),
]

for label_w, val_w, col_w in waterfall_items:
    add_para(tf_s6_l, f"{label_w}:  {val_w}", size=13, color=col_w, bold=True, space_after=8)

add_para(tf_s6_l, "Shared pit lane transit time cancels out because both cars must stop. The margin depends entirely on out-lap pace and traffic.", size=11, color=MUTED, space_after=0)

# Right Column: Uncertainty & Stress Testing
c_s6_r = add_card(s6, 6.8, 1.6, 5.7, 5.2)
tf_s6_r = c_s6_r.text_frame
tf_s6_r.margin_left = tf_s6_r.margin_right = Inches(0.3)
tf_s6_r.margin_top = Inches(0.25)

add_para(tf_s6_r, "STRESS TESTING FRAGILE ASSUMPTIONS", size=16, color=ORANGE, bold=True, space_after=8)
add_para(tf_s6_r, "In Formula 1, pit stops fail because teams assume deterministic clean air. PITWALL surfaces the variance:", size=12, color=WHITE, space_after=12)

add_para(tf_s6_r, "EMPIRICAL UNCERTAINTY BANDS", size=12, color=LIME, bold=True, space_after=3)
add_para(tf_s6_r, "Clean Rejoin Interval:  −6.93 s  to  +10.26 s\nStressed Traffic Interval:  −8.93 s  to  +8.26 s", size=13, color=WHITE, bold=True, space_after=12)

add_para(tf_s6_r, "CRITICAL INSIGHT FOR THE RACE STRATEGIST", size=12, color=ORANGE, bold=True, space_after=3)
add_para(tf_s6_r, "Because both confidence intervals cross zero, the undercut is NOT a guaranteed overtake. A 2-second rejoin traffic delay flips the expected value negative.", size=12, color=DIM, space_after=14)

add_para(tf_s6_r, "DECISION SUPPORT, NOT BLACK-BOX COMMANDS", size=12, color=LIME, bold=True, space_after=3)
add_para(tf_s6_r, "Rather than barking 'Box now', PITWALL reveals the critical traffic threshold so the strategist can abort if a backmarker doesn't yield.", size=12, color=DIM, space_after=0)


# ============================================================================ #
# SLIDE 7: EMPIRICAL BENCHMARKS & RIGOROUS EVALUATION
# ============================================================================ #
s7_notes = (
    "Let's look at the hard benchmark numbers. We tested PITWALL across 12 Grand Prix events of the 2026 season. "
    "Across 6,831 scored chronological pace forecasts, PITWALL achieved a 0.743s RMSE—a 12.0% improvement over persistence. "
    "For relative battle times against rivals, RMSE was 2.197s—10.0% better than rolling median extrapolation. "
    "Most importantly for strategy: when alerting that a driver is about to lose >2 seconds to a rival, "
    "our precision is 78.1% compared to 71.3% for baselines, eliminating 73 costly false alarms."
)
s7 = create_slide(notes=s7_notes)
add_header(s7, "06 / BENCHMARK RESULTS", "Rigorous Chronological Evaluation Across 12 Races")

# Top 4 Metric Cards
metrics = [
    ("PACE FORECAST RMSE", "0.743 s", "12.0% Lower Error", "vs 0.844s persistence (6,831 forecasts)"),
    ("RIVAL BATTLE RMSE", "2.197 s", "10.0% Lower Error", "vs 2.441s rolling median (3,128 battles)"),
    ("LOSS ALERT PRECISION", "78.1 %", "+6.8% Accuracy", "Alerts for losing >2s (saves 73 false alarms)"),
    ("PIT STOP RECOVERY", "0.672 s", "11.8% Lower Error", "vs 0.761s season mean (107 race stops)")
]

for i, (m_title, m_val, m_badge, m_sub) in enumerate(metrics):
    c_m = add_card(s7, 0.8 + i * 2.95, 1.6, 2.8, 1.8)
    tf_m = c_m.text_frame
    tf_m.margin_left = tf_m.margin_right = Inches(0.2)
    tf_m.margin_top = Inches(0.18)
    add_para(tf_m, m_title, size=10, color=MUTED, bold=True, space_after=2)
    add_para(tf_m, m_val, size=24, color=LIME, bold=True, space_after=2)
    add_para(tf_m, m_badge, size=12, color=ORANGE, bold=True, space_after=2)
    add_para(tf_m, m_sub, size=10, color=DIM, space_after=0)

# Lower Section: Benchmark Summary Table
c_table = add_card(s7, 0.8, 3.65, 11.733, 3.15)
tf_tab = c_table.text_frame
tf_tab.margin_left = tf_tab.margin_right = Inches(0.3)
tf_tab.margin_top = Inches(0.25)

add_para(tf_tab, "CHRONOLOGICAL BENCHMARK AUDIT (EXPANDING WINDOW TRAINING THROUGH R08, REUSED EVALUATION R09–R12)", size=12, color=LIME, bold=True, space_after=12)

table_rows = [
    ("TASK / TARGET", "PITWALL MODEL", "BENCHMARK BASELINE", "IMPROVEMENT", "SAMPLE SIZE (N)"),
    ("Future Lap Pace (1 to 3 laps)", "0.743 s RMSE", "0.844 s (Persistence)", "12.0% lower error", "6,831 scored laps"),
    ("Rival Gap Evolution", "2.197 s RMSE", "2.441 s (Rolling Median)", "10.0% lower error", "3,128 battles"),
    ("Rival Loss Alert (>2.0s lost)", "78.1% Precision", "71.3% Precision", "+6.8% precision", "73 false alerts cut"),
    ("Pit Stop Rubber Gain", "0.672 s RMSE", "0.761 s (Historical Mean)", "11.8% lower error", "107 validated stops"),
    ("Pace Interval Coverage", "92.5% empirical", "90.0% nominal target", "Well-calibrated", "6,831 forecasts")
]

for row_idx, r in enumerate(table_rows):
    is_hdr = (row_idx == 0)
    col_str = f"{r[0]:<30} | {r[1]:<20} | {r[2]:<25} | {r[3]:<18} | {r[4]}"
    add_para(tf_tab, col_str, size=11, color=LIME if is_hdr else WHITE, bold=is_hdr, space_after=4)


# ============================================================================ #
# SLIDE 8: SYSTEM ARCHITECTURE & DATA ENGINEERING
# ============================================================================ #
s8_notes = (
    "Behind PITWALL is a rock-solid, production-grade engineering architecture. "
    "We ingest raw telemetry, timing, and weather feeds via FastF1, encompassing 14,310 laps across 12 events. "
    "Our modeling pipeline evaluates 17 pace model specifications and 8 stop specifications, selecting regularized "
    "Ridge with saturating age bases and state-space estimation. "
    "The frontend is zero-dependency, static, and works completely offline—critical for trackside deployment."
)
s8 = create_slide(notes=s8_notes)
add_header(s8, "07 / SYSTEM ARCHITECTURE", "End-to-End Motorsport Data & Machine Learning Pipeline")

pipeline_stages = [
    ("INGESTION & CLEANING", "FastF1 2026 Season",
     "• 12 Grand Prix events (14,310 laps)\n• Sub-second driver spatial telemetry\n• Weather & track temperature feeds\n• Strict filtering of safety cars & out-laps"),
    ("FEATURE ENGINEERING", "Physics Identification",
     "• Estimated fuel lambda (-0.0294 s/kg)\n• Track evolution saturation log-basis\n• Measured traffic proximity gaps\n• Saturating tyre age basis functions"),
    ("MODEL ENSEMBLE", "Robust Chronological ML",
     "• 17 Pace candidates evaluated\n• State-space pace estimation + Ridge\n• Battle relative-correction models\n• Calibrated uncertainty prediction bands"),
    ("OFFLINE RACE CONSOLE", "High-Performance UI",
     "• 100% Client-side HTML5/Vanilla JS\n• Synchronized circuit spatial replay\n• One Driver Clock telemetry alignment\n• Portable zero-cloud jury deployment")
]

for i, (p_title, p_sub, p_desc) in enumerate(pipeline_stages):
    c_p = add_card(s8, 0.8 + i * 2.95, 1.6, 2.8, 5.2)
    tf_p = c_p.text_frame
    tf_p.margin_left = tf_p.margin_right = Inches(0.2)
    tf_p.margin_top = Inches(0.25)
    
    add_para(tf_p, f"LAYER 0{i+1}", size=11, color=LIME, bold=True, space_after=2)
    add_para(tf_p, p_title, size=15, color=WHITE, bold=True, space_after=4)
    add_para(tf_p, p_sub, size=12, color=ORANGE, bold=True, space_after=14)
    add_para(tf_p, p_desc, size=12, color=DIM, space_after=0)


# ============================================================================ #
# SLIDE 9: SCIENTIFIC INTEGRITY & ETHICAL BOUNDARIES
# ============================================================================ #
s9_notes = (
    "A winning hackathon submission must demonstrate scientific integrity. "
    "We are completely transparent about our modeling boundaries: "
    "First, we disclose that R09 to R12 are reused evaluation races, not a fresh blind holdout. "
    "Second, we do not hallucinate physical tyre sensors: carcass temperature, pressure, and surface wear are "
    "not in public feeds, and we state that clearly in the console. "
    "Third, we make no unvalidated claims of 'positions won' in counterfactual races. "
    "We present audited forecasting improvements and robust decision stress tests."
)
s9 = create_slide(notes=s9_notes)
add_header(s9, "08 / SCIENTIFIC INTEGRITY", "Transparent Modeling Boundaries & Engineering Rigor")

pillars = [
    ("HONEST REUSED EVALUATION",
     "Races R09–R12 were inspected during previous revisions. We transparently report them as a reused evaluation set with expanding historical training, rather than claiming an unexamined blind trial."),
    ("NO SENSOR HALLUCINATION",
     "Formula 1 teams guard internal tyre carcass temperatures and pressure sensors. Rather than hallucinating fake physical wear percentages, PITWALL models observable pace steps and flags missing telemetry."),
    ("NO UNVALIDATED 'POSITIONS WON' CLAIMS",
     "Winning an undercut depends on competitor pit crew times, traffic, and track evolution. We price the required attack budget and report interval overlaps rather than making wild counterfactual win claims."),
    ("EXPLICIT ABSTENTION LOGIC",
     "When safety cars neutralize the race, timing loops drop, or scenarios lack sufficient historical support, PITWALL explicitly outputs 'unsupported / uncertain' instead of outputting dangerous guesses.")
]

for i, (p_head, p_body) in enumerate(pillars):
    row = i // 2
    col = i % 2
    c_pil = add_card(s9, 0.8 + col * 5.95, 1.6 + row * 2.65, 5.75, 2.45)
    tf_pil = c_pil.text_frame
    tf_pil.margin_left = tf_pil.margin_right = Inches(0.3)
    tf_pil.margin_top = Inches(0.2)
    add_para(tf_pil, p_head, size=14, color=LIME, bold=True, space_after=6)
    add_para(tf_pil, p_body, size=12, color=WHITE, space_after=0)


# ============================================================================ #
# SLIDE 10: CONCLUSION & SUMMARY
# ============================================================================ #
s10_notes = (
    "In conclusion, PITWALL bridges the gap between deep motorsport data science and real-time pit wall decision making. "
    "We solve the fuel collinearity trap, provide verified chronological pace forecasting with a 12% lower RMSE, "
    "and give strategists an inspectable attack budget to prevent costly undercut failures. "
    "Thank you to the jury and organizers of TrackShift 2026. Aditya and Ruhani are now ready for your questions!"
)
s10 = create_slide(notes=s10_notes)
add_header(s10, "09 / SUMMARY & CONCLUSION", "PITWALL: The Strategic Advantage on Track")

# Summary highlights in 3 cards
concl_data = [
    ("THE CORE INNOVATION", "Physics Deconfounding",
     "Discovered and proved why practice degradation curves fail to transfer to race day. Replaced collinearity with observable pit-step pace recovery modeling (+1.26s/lap)."),
    ("THE MEASURED ADVANTAGE", "Audited Benchmarks",
     "12.0% lower lap pace RMSE across 6,831 forecasts, 10.0% lower battle gap RMSE, and 78.1% alert precision, validated across 12 Formula 1 Grand Prix events."),
    ("THE WORKING PRODUCT", "Zero-Cloud Race Console",
     "Live 4.349 km circuit reconstruction with One Driver Clock synchronization, auto-verified forecast locks, and interactive undercut traffic stress-testing.")
]

for i, (c_tag, c_head, c_desc) in enumerate(concl_data):
    c_end = add_card(s10, 0.8 + i * 3.95, 1.6, 3.75, 3.5)
    tf_end = c_end.text_frame
    tf_end.margin_left = tf_end.margin_right = Inches(0.25)
    tf_end.margin_top = Inches(0.25)
    add_para(tf_end, c_tag, size=11, color=ORANGE, bold=True, space_after=4)
    add_para(tf_end, c_head, size=16, color=LIME, bold=True, space_after=12)
    add_para(tf_end, c_desc, size=13, color=WHITE, space_after=0)

# Team & Q&A Box
c_qa = add_card(s10, 0.8, 5.35, 11.733, 1.65, bg=CARD_BG, border=LIME)
tf_qa = c_qa.text_frame
tf_qa.margin_left = tf_qa.margin_right = Inches(0.3)
tf_qa.margin_top = Inches(0.2)
add_para(tf_qa, "THANK YOU  —  TEAM HANDSOME SQUIDWARD", size=18, color=LIME, bold=True, space_after=4)
add_para(tf_qa, "Team Members: Aditya & Ruhani   |   Hackathon: TrackShift 2026   |   AI Motorsport Track", size=13, color=WHITE, bold=True, space_after=4)
add_para(tf_qa, "Demo Live at: scripts/serve_demo.py --port 8001  ->  http://127.0.0.1:8001/demo_fallback/", size=12, color=DIM, space_after=0)

# Save both
prs.save(OUT_FINAL)
prs.save(OUT_UPDATED)
print(f"Presentation successfully saved to:\n  - {OUT_FINAL}\n  - {OUT_UPDATED}")
