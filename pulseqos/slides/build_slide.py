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
# UI lane
node(X0, 1.22, 3.05, 0.52, "Focus Mode app / REST API", "“protect my call for 30 min” • authenticated, rate-limited")
node(X0 + 3.15, 1.22, 3.32, 0.52, "Dashboard + “Why” panel", "p95 delay, jitter, loss, queue, Jain • audit timeline")
# Analytics lane
node(X0, 1.90, 2.05, 1.2, "FAST LOOP (≤ 1 s)", "Capacity estimator\nOWD / RTT under load\nAIMD shaper rate\n(rate cuts skip trial)", dark=True)
node(X0 + 2.15, 1.90, 2.15, 1.2, "SLOW LOOP (10–30 s)", "Policy controller\ndeterministic rules +\nsafe action menu,\nhysteresis, hold time", dark=True)
node(X0 + 4.4, 1.90, 2.07, 1.2, "Safety gate", "validate → bounded\nlive trial → keep or\nroll back whole bundle\n+ watchdog → safe state")
# Data lane
node(X0, 3.25, 6.47, 0.44, "Flow table (conntrack) • telemetry store • versioned policy bundles • audit log", "", size=8.5)
# Edge lane
node(X0, 3.84, 2.05, 0.88, "Flow classifier", "sizes, timing, direction\ncalibrated conf. + Unknown")
node(X0 + 2.15, 3.84, 2.15, 0.88, "Mark per flow", "class → conntrack mark\n(user correction wins)")
node(X0 + 4.4, 3.84, 2.07, 0.88, "Linux tc enforcement", "CAKE on WAN + IFB\n(ctinfo restore) • HTB variant")
# Device & network lane
node(X0, 4.88, 3.05, 0.52, "Home devices (emulated)", "laptop call • console • 3 TVs • 15 GB download")
node(X0 + 3.15, 4.88, 3.32, 0.52, "WAN bottleneck (emulated)", "token bucket + netem • 100 → 20 Mbps • IPv4/IPv6")

# arrows (vertical flow hints)
for (x1, y1, x2, y2) in [
    (X0 + 1.02, 4.88, X0 + 1.02, 4.72),        # devices -> classifier
    (X0 + 2.05, 4.28, X0 + 2.15, 4.28),        # classifier -> mark
    (X0 + 4.30, 4.28, X0 + 4.40, 4.28),        # mark -> tc
    (X0 + 5.43, 4.72, X0 + 5.43, 4.88),        # tc -> WAN
    (X0 + 3.22, 3.10, X0 + 3.22, 3.25),        # controller -> data
    (X0 + 4.30, 2.50, X0 + 4.40, 2.50),        # controller -> safety gate
    (X0 + 5.43, 3.10, X0 + 5.43, 3.84),        # gate -> tc
    (X0 + 1.52, 1.74, X0 + 1.52, 1.90),        # intent -> analytics
]:
    arrow(s, x1, y1, x2, y2)

# key fixes strip under the diagram
kf = box(s, lx, 5.52, lw, 1.42, WHITE, line=BLUE, shape=MSO_SHAPE.RECTANGLE)
text(kf, [
    [("DESIGN RULES THAT KEEP IT CORRECT", True, BLUE)],
    [("▸ ", True, BLUE), ("Tins: ", True, NAVY), ("call audio + gaming → Voice; call video → Video (RFC 8837 WebRTC marking); bulk → Bulk; Unknown never boosted", False, GREY)],
    [("▸ ", True, BLUE), ("Trust: ", True, NAVY), ("inbound DSCP from the Internet is ignored; download class is restored from our own conntrack mark", False, GREY)],
    [("▸ ", True, BLUE), ("Two speeds: ", True, NAVY), ("capacity cuts act within a second; policy changes wait for the safety gate, so a link drop is never blocked by anti-flap rules", False, GREY)],
    [("▸ ", True, BLUE), ("Privacy: ", True, NAVY), ("metadata only, no payload or domain logging; per-device views only to the account owner", False, GREY)],
], size=10.5)
for par in kf.text_frame.paragraphs:
    par.space_after = Pt(3)

# ---- Right column ----
rx, rw = 8.05, 4.98
eh = box(s, rx, 0.9, rw, 0.36, NAVY, shape=MSO_SHAPE.RECTANGLE)
text(eh, [[("PILOT EVIDENCE — measured, not assumed", True, YEL)]], size=11, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
eb = box(s, rx, 1.26, rw, 2.62, WHITE, line=NAVY, shape=MSO_SHAPE.RECTANGLE)

cd = CategoryChartData()
cd.categories = ["FIFO (no QoS)", "Class shaping (HTB layout)"]
cd.add_series("p95 call-probe delay (ms)", (138.0, 0.07))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(rx + 0.05), Inches(1.3), Inches(rw - 0.1), Inches(1.45), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "p95 call-probe delay during a 4-stream download (ms)"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(9.5)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
ch.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = NAVY
plot = ch.plots[0]
plot.gap_width = 60
plot.has_data_labels = True
dl = plot.data_labels
dl.font.size = Pt(10)
dl.font.bold = True
dl.number_format = '#,##0.0#'
dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
ser = plot.series[0]
for i, c in enumerate((RED, GREEN)):
    pt = ser.points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = c
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.maximum_scale = 240
ch.category_axis.tick_labels.font.size = Pt(9)
ch.category_axis.format.line.fill.background()

ev = s.shapes.add_textbox(Inches(rx + 0.05), Inches(2.76), Inches(rw - 0.1), Inches(1.1))
text(ev, [
    [("Same download goodput in both: ", True, NAVY), ("18.7 Mbps of 20 — the call is protected without starving bulk.", False, GREY)],
    [("Setup: ", True, NAVY), ("Linux namespaces, 20 Mbit bottleneck, 50 pkt/s probes, 5 paired runs (medians; FIFO range 128–152 ms). "
      "Emulation; no WAN delay or Wi-Fi; ideal classification. Round 2 repeats this with CAKE, netem and all baselines.", False, GREY)],
], size=9.5)

dh = box(s, rx, 4.0, rw, 0.36, BLUE, shape=MSO_SHAPE.RECTANGLE)
text(dh, [[("UNDERSTAND → DECIDE → PROTECT → PROVE", True, WHITE)]], size=11, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
db = box(s, rx, 4.36, rw, 2.58, WHITE, line=BLUE, shape=MSO_SHAPE.RECTANGLE)
text(db, [
    [("▸ Understand: ", True, NAVY), ("LightGBM on flow metadata, trained on real app captures, split by session; reports confidence, abstains to Unknown; "
                                            "metrics: macro-F1, wrong-boost rate, time-to-classify.", False, GREY)],
    [("▸ Decide: ", True, NAVY), ("Focus Mode with auto-expiry, priority ceiling and a daily Fairness Budget; "
                                       "a learned tuner stays only if it beats the rule controller in A/B runs.", False, GREY)],
    [("▸ Protect: ", True, NAVY), ("fast-abort on call latency, whole-bundle rollback with read-back check, watchdog → known safe state.", False, GREY)],
    [("▸ Prove: ", True, NAVY), ("one command runs 9 scenarios × 6 systems (FIFO, CAKE, CAKE+autorate, rule QoS, ours, ours+ML), "
                                      "10 runs each: p95/p99 delay, jitter, loss, RPM, Jain, settle time, CPU.", False, GREY)],
], size=10.5)
for par in db.text_frame.paragraphs:
    par.space_after = Pt(4)

foot = s.shapes.add_textbox(Inches(0.3), Inches(7.0), Inches(12.73), Inches(0.4))
text(foot, [[("Boundary: ", True, NAVY),
             ("reference implementation in emulation, labelled as such. A product also needs router hardware, flow-offload handling, "
              "gigabit CPU budget, Wi-Fi airtime fairness and a security review of the intent API.", False, GREY)]],
     size=9, align=PP_ALIGN.CENTER)

notes = s.notes_slide.notes_text_frame
notes.text = (
    "60-second pitch: Home links carry calls, games, TVs and downloads at once. Big queues, not low bandwidth, ruin calls. "
    "PulseQoS sits on proven Linux CAKE and adds four things: it understands traffic from metadata only and admits uncertainty; "
    "it follows the real link speed within a second; it takes a temporary user intent with expiry and a fairness budget; "
    "and it verifies every policy change, rolling back if the call gets worse. Our pilot already shows the problem and the fix: "
    "a download pushed call-probe p95 delay to 138 ms on FIFO and kept it under 0.1 ms with class shaping, with identical download goodput. "
    "Round 2 measures PulseQoS against CAKE and CAKE-autorate, not just against no QoS."
)

p.save(out)
