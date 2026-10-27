import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

src, out = sys.argv[1], sys.argv[2]
p = Presentation(src)

BLUE = RGBColor(0x00, 0x8C, 0xC8)
NAVY = RGBColor(0x0B, 0x2E, 0x4F)
YEL = RGBColor(0xF5, 0xB4, 0x00)
LIGHT = RGBColor(0xE8, 0xF5, 0xFC)
GREY = RGBColor(0x33, 0x33, 0x33)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def text(shape, runs, size=10, color=GREY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """runs: list of paragraphs; each paragraph is str or list of (text, bold, color)."""
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(0.06))
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, para in enumerate(runs):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = align
        if isinstance(para, str):
            para = [(para, False, color)]
        for t, b, c in para:
            r = par.add_run()
            r.text = t
            r.font.size = Pt(size)
            r.font.bold = b
            r.font.color.rgb = c or color
            r.font.name = "Calibri"


def box(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.12
    return s


def arrow(slide, x1, y1, x2, y2, color=NAVY):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.5)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"})
    ln.append(tail)
    return c


from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION

RED = RGBColor(0xD9, 0x3A, 0x2B)
GREEN = RGBColor(0x1E, 0x8E, 0x3E)

# ---------- Slide 1: cover ----------
s1 = p.slides[0]
for sh in s1.shapes:
    if sh.has_text_frame and sh.text_frame.text.strip().startswith("Case Study No"):
        sh.text_frame.paragraphs[0].runs[0].text = "Case Study No. 3 – Adaptive QoS Engine (PulseQoS)"
        sh.left, sh.width = Inches(1.5), Inches(10.33)
    elif sh.is_placeholder and sh.placeholder_format.idx == 1:
        tf = sh.text_frame
        tf.text = "Manas Girdhar (Team Leader)"
        for line in ["Meenakshi Satpathy", "Birla Institute of Technology, Mesra"]:
            tf.add_paragraph().text = line

# ---------- Slide 2 ----------
s = p.slides[1]
for sh in list(s.shapes):
    if sh.is_placeholder and sh.placeholder_format.idx == 1:
        sh._element.getparent().remove(sh._element)
    elif sh.is_placeholder:
        title = sh

title.left, title.top, title.width, title.height = Inches(2.7), Inches(0.08), Inches(8.0), Inches(0.72)
text(title, [[("PulseQoS: ", True, BLUE), ("the call never notices the download", True, NAVY)],
             [("Intent-aware, self-verifying QoS controller for home broadband — payload-blind, built on open Linux tc", False, GREY)]],
     size=20, anchor=MSO_ANCHOR.MIDDLE)
title.text_frame.paragraphs[1].runs[0].font.size = Pt(11.5)

# ---- Left: layered architecture (device / edge / network / data / analytics / UI) ----
lx, lw = 0.3, 7.55
hdr = s.shapes.add_textbox(Inches(lx), Inches(0.86), Inches(lw), Inches(0.3))
text(hdr, [[("ARCHITECTURE — one closed loop, two speeds", True, BLUE)]], size=10.5)

lanes = [  # (label, y, h)
    ("UI", 1.17, 0.62),
    ("ANALYTICS\n& CONTROL", 1.85, 1.30),
    ("DATA", 3.21, 0.52),
    ("EDGE\n(router)", 3.79, 0.98),
    ("DEVICE &\nNETWORK", 4.83, 0.62),
]
LANEBG = RGBColor(0xF4, 0xF9, 0xFD)
for lab, y, h in lanes:
    bg = box(s, lx, y, lw, h, LANEBG, shape=MSO_SHAPE.RECTANGLE)
    lb = box(s, lx, y, 0.88, h, BLUE, shape=MSO_SHAPE.RECTANGLE)
    text(lb, [[(l, True, WHITE)] for l in lab.split("\n")], size=8.5, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def node(x, y, w, h, head, body, dark=False, size=8.5):
    b = box(s, x, y, w, h, NAVY if dark else WHITE, line=None if dark else BLUE)
    b.adjustments[0] = 0.08
    text(b, [[(head, True, YEL if dark else NAVY)]] + [[(l, False, WHITE if dark else GREY)] for l in body.split("\n")],
         size=size, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    b.text_frame.paragraphs[0].runs[0].font.size = Pt(size + 1)
    return b


X0 = lx + 0.98
PURPLE = RGBColor(0x7A, 0x3F, 0xC9)


def ainode(x, y, w, h, head, body, size=8):
    b = box(s, x, y, w, h, PURPLE)
    b.adjustments[0] = 0.08
    text(b, [[(head, True, WHITE)]] + [[(l, False, WHITE)] for l in body.split("\n")],
         size=size, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    b.text_frame.paragraphs[0].runs[0].font.size = Pt(size + 1)
    return b


# UI lane
node(X0, 1.22, 3.05, 0.52, "Focus Mode app / REST API", "manual intent or Zero-click auto-protect • 1-tap undo")
node(X0 + 3.15, 1.22, 3.32, 0.52, "Dashboard + “Why” panel", "p95, jitter, loss, queue, Jain, RPM • Twin prediction vs real")
# Analytics lane: fast loop | slow loop | Twin (AI) | safety gate
w4 = 1.55
node(X0, 1.90, w4, 1.2, "FAST LOOP ≤ 1 s", "capacity estimator\none-way delay\nrate cuts act at\nonce, skip trial", dark=True, size=8)
node(X0 + 1.64, 1.90, w4, 1.2, "SLOW LOOP 10–30 s", "policy controller\nsafe action menu\nhysteresis +\nhold time", dark=True, size=8)
ainode(X0 + 3.28, 1.90, w4, 1.2, "AI  Experience Twin", "predicts next-10 s\ncall delay for each\naction; drops unsafe\nones before users feel")
node(X0 + 4.92, 1.90, w4, 1.2, "Safety gate", "validate → live\ntrial → keep or\nroll back • watchdog\n→ safe state", size=8)
# Data lane
node(X0, 3.25, 6.47, 0.44, "Flow table (conntrack) • telemetry • versioned policy bundles • audit log • Twin training set", "", size=8.5)
# Edge lane
ainode(X0, 3.84, 2.05, 0.88, "AI  Conformal classifier", "metadata only • boosts only\nwhen certain, else Unknown", size=8.5)
node(X0 + 2.15, 3.84, 2.15, 0.88, "One mark per flow", "class → conntrack mark\nrestored both ways (ctinfo)")
node(X0 + 4.4, 3.84, 2.07, 0.88, "Linux tc enforcement", "CAKE on WAN + IFB\nHTB variant for floors")
# Device & network lane
node(X0, 4.88, 3.05, 0.52, "Home devices (emulated)", "laptop calls • console • 3 TVs • 15 GB download")
node(X0 + 3.15, 4.88, 3.32, 0.52, "WAN bottleneck (emulated)", "token bucket + netem • 100 → 20 Mbps • IPv4/IPv6")

for (x1, y1, x2, y2) in [
    (X0 + 1.02, 4.88, X0 + 1.02, 4.72),
    (X0 + 2.05, 4.28, X0 + 2.15, 4.28),
    (X0 + 4.30, 4.28, X0 + 4.40, 4.28),
    (X0 + 5.43, 4.72, X0 + 5.43, 4.88),
    (X0 + 3.19, 2.50, X0 + 3.28, 2.50),
    (X0 + 4.83, 2.50, X0 + 4.92, 2.50),
    (X0 + 6.30, 3.10, X0 + 6.30, 3.84),
    (X0 + 0.78, 3.10, X0 + 0.78, 3.25),
    (X0 + 1.52, 1.74, X0 + 1.52, 1.90),
]:
    arrow(s, x1, y1, x2, y2)

kf = box(s, lx, 5.52, lw, 1.42, WHITE, line=BLUE, shape=MSO_SHAPE.RECTANGLE)
text(kf, [
    [("DESIGN RULES THAT KEEP IT CORRECT", True, BLUE)],
    [("▸ ", True, BLUE), ("Tins: ", True, NAVY), ("call audio + gaming → Voice; call video → Video (Voice tin is only 25%; RFC 8837); Unknown never boosted", False, GREY)],
    [("▸ ", True, BLUE), ("Trust: ", True, NAVY), ("Internet DSCP is cleared on arrival; only our own conntrack mark sets priority", False, GREY)],
    [("▸ ", True, BLUE), ("Link realism: ", True, NAVY), ("overhead compensation, upload ACK filter, per-direction one-way delay", False, GREY)],
    [("▸ ", True, BLUE), ("Privacy & abuse: ", True, NAVY), ("no payload or domain logging; LAN-only authenticated intent API with budgets", False, GREY)],
], size=10)
for par in kf.text_frame.paragraphs:
    par.space_after = Pt(4)

# ---- Right column: AI layer ----
rx, rw = 8.05, 4.98
ah = box(s, rx, 0.9, rw, 0.36, PURPLE, shape=MSO_SHAPE.RECTANGLE)
text(ah, [[("THE AI ONLY PULSEQOS HAS — each must beat a rule-based twin", True, WHITE)]], size=10.5, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
ab = box(s, rx, 1.26, rw, 2.92, WHITE, line=PURPLE, shape=MSO_SHAPE.RECTANGLE)
text(ab, [
    [("1  Conformal classifier. ", True, PURPLE), ("Boosts a flow only when its prediction set is a single call/game class, so wrong boosts stay "
      "≤ a chosen rate (e.g. 1%) by construction on calibration-like traffic. ", False, GREY), ("vs port rules", True, NAVY)],
    [("2  Experience Twin. ", True, PURPLE), ("Learned model of the home link (trained offline in the lab, never by exploring on users) "
      "predicts each change’s effect and rejects harmful ones before they go live. ", False, GREY), ("metric: harm-seconds avoided", True, NAVY)],
    [("3  Zero-click Focus. ", True, PURPLE), ("Detects a call starting on a busy link and protects it within seconds, "
      "charged to a Fairness Budget, with undo. ", False, GREY), ("metric: time-to-protection", True, NAVY)],
    [("No chatbot: ", True, NAVY), ("the case asks AI to improve a measurable outcome, not add a chat interface. An AI part that loses its A/B test is switched off.", False, GREY)],
], size=10.5)
for par in ab.text_frame.paragraphs:
    par.space_after = Pt(4)

eh = box(s, rx, 4.28, rw, 0.32, NAVY, shape=MSO_SHAPE.RECTANGLE)
text(eh, [[("PILOT EVIDENCE — measured 27 Oct, not assumed", True, YEL)]], size=10.5, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
eb = box(s, rx, 4.6, rw, 2.34, WHITE, line=NAVY, shape=MSO_SHAPE.RECTANGLE)

cd = CategoryChartData()
cd.categories = ["FIFO (no QoS)", "Class shaping (HTB)"]
cd.add_series("p95 call-probe delay (ms)", (138.0, 0.07))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(rx + 0.05), Inches(4.62), Inches(rw - 0.1), Inches(1.2), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "p95 call-probe delay during a 4-stream download (ms)"
r0 = ch.chart_title.text_frame.paragraphs[0].runs[0]
r0.font.size = Pt(9); r0.font.bold = True; r0.font.color.rgb = NAVY
plot = ch.plots[0]
plot.gap_width = 50
plot.has_data_labels = True
dl = plot.data_labels
dl.font.size = Pt(10); dl.font.bold = True
dl.number_format = '#,##0.0#'; dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
for i, c in enumerate((RED, GREEN)):
    pt = plot.series[0].points[i]
    pt.format.fill.solid(); pt.format.fill.fore_color.rgb = c
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.maximum_scale = 240
ch.category_axis.tick_labels.font.size = Pt(9)
ch.category_axis.format.line.fill.background()

ev = s.shapes.add_textbox(Inches(rx + 0.05), Inches(5.8), Inches(rw - 0.1), Inches(1.12))
text(ev, [
    [("Download goodput identical: ", True, NAVY), ("18.7 of 20 Mbps — call protected, bulk not starved.", False, GREY)],
    [("5 paired runs, Linux namespaces, 20 Mbit link; emulation without WAN delay, ideal classification. "
      "Round 2: CAKE, netem, 8 systems × 14 scenarios × 10 runs, incl. CAKE’s own autorate.", False, GREY)],
], size=9)

foot = s.shapes.add_textbox(Inches(0.3), Inches(7.0), Inches(12.73), Inches(0.4))
text(foot, [[("Boundary: ", True, NAVY),
             ("reference implementation in emulation, labelled as such. A product also needs router hardware, flow-offload handling, "
              "gigabit CPU budget, Wi-Fi airtime fairness and certification.", False, GREY)]],
     size=9, align=PP_ALIGN.CENTER)

notes = s.notes_slide.notes_text_frame
notes.text = (
    "60-second pitch: Home links carry calls, games, TVs and downloads at once; big queues, not low bandwidth, ruin calls. "
    "PulseQoS runs on proven Linux CAKE with a fast loop that follows the real link speed within a second, and a slow, safety-gated loop for policy. "
    "Our AI layer is what nobody else has, and each part must beat a rule-based twin: a conformal classifier that only boosts traffic when it is certain, "
    "so wrong boosts stay under a chosen rate; an Experience Twin, a learned model of the home link that predicts the effect of every change "
    "and rejects harmful ones before users feel them; and Zero-click Focus, which protects a call the moment it starts, with a fairness budget and undo. "
    "Our pilot already shows the problem and the fix: a download pushed call delay to 138 ms on FIFO; class shaping kept it under 0.1 ms with the same download speed. "
    "In Round 2 we measure against CAKE and its autorate, not just against no QoS."
)

p.save(out)
