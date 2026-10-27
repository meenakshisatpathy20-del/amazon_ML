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
        sh.text_frame.paragraphs[0].runs[0].text = "Case Study No. 3"
        sh.left, sh.width = Inches(1.5), Inches(10.33)
    elif sh.is_placeholder and sh.placeholder_format.idx == 1:
        tf = sh.text_frame
        tf.text = "Team MM"
        tf.paragraphs[0].runs[0].font.bold = True
        for line in ["Manas Girdhar (Team Leader)", "Meenakshi Satpathy", "Birla Institute of Technology, Mesra"]:
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
             [("An adaptive QoS controller for home broadband, built on Linux tc and CAKE. No payload inspection.", False, GREY)]],
     size=20, anchor=MSO_ANCHOR.MIDDLE)
title.text_frame.paragraphs[1].runs[0].font.size = Pt(11.5)

# ---- Left: layered architecture (device / edge / network / data / analytics / UI) ----
lx, lw = 0.3, 7.55
hdr = s.shapes.add_textbox(Inches(lx), Inches(0.86), Inches(lw), Inches(0.3))
text(hdr, [[("System architecture", True, BLUE)]], size=10.5)

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
PURPLE = RGBColor(0x2B, 0x6C, 0xB0)


def ainode(x, y, w, h, head, body, size=8):
    b = box(s, x, y, w, h, PURPLE)
    b.adjustments[0] = 0.08
    text(b, [[(head, True, WHITE)]] + [[(l, False, WHITE)] for l in body.split("\n")],
         size=size, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    b.text_frame.paragraphs[0].runs[0].font.size = Pt(size + 1)
    return b


# UI lane
node(X0, 1.22, 3.05, 0.52, "Focus Mode app / REST API", "protect a call for N minutes; auto-protect has undo")
node(X0 + 3.15, 1.22, 3.32, 0.52, "Dashboard + \u201cWhy\u201d panel", "latency, jitter, loss, queue depth, fairness; reason for each change")
# Analytics lane: fast loop | slow loop | Twin (AI) | safety gate
w4 = 1.55
node(X0, 1.90, w4, 1.2, "Rate loop (1 s)", "capacity estimator\nusing one-way delay;\nlowers shaper rate\nimmediately", dark=True, size=8)
node(X0 + 1.64, 1.90, w4, 1.2, "Policy loop (10-30 s)", "rule-based controller\nfixed set of allowed\nactions, hysteresis,\nminimum hold time", dark=True, size=8)
ainode(X0 + 3.28, 1.90, w4, 1.2, "Link model (ML)", "predicts call delay\nfor each candidate\naction; filters out\nrisky ones")
node(X0 + 4.92, 1.90, w4, 1.2, "Safety check", "validate, short live\ntrial, keep or roll\nback; watchdog falls\nback to plain CAKE", size=8)
# Data lane
node(X0, 3.25, 6.47, 0.44, "Flow table (conntrack), telemetry store, versioned policies, audit log", "", size=8.5)
# Edge lane
ainode(X0, 3.84, 2.05, 0.88, "Flow classifier (ML)", "packet sizes and timing only;\nunsure flows stay best effort", size=8.5)
node(X0 + 2.15, 3.84, 2.15, 0.88, "Flow marking", "class stored in conntrack\nmark, restored with ctinfo")
node(X0 + 4.4, 3.84, 2.07, 0.88, "Linux tc", "CAKE on WAN and IFB;\nHTB variant for hard floors")
# Device & network lane
node(X0, 4.88, 3.05, 0.52, "Home devices (emulated)", "laptop on a call, console, 3 TVs, a large download")
node(X0 + 3.15, 4.88, 3.32, 0.52, "WAN link (emulated)", "netem + token bucket, 100 to 20 Mbps, IPv4 and IPv6")

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
    [("Key design decisions", True, BLUE)],
    [("\u2022 ", True, BLUE), ("Tins: ", True, NAVY), ("call audio and games go to the Voice tin, call video to the Video tin (Voice is capped at 25% in diffserv4)", False, GREY)],
    [("\u2022 ", True, BLUE), ("Trust: ", True, NAVY), ("DSCP marks coming from the Internet are cleared, so outside traffic cannot claim priority", False, GREY)],
    [("\u2022 ", True, BLUE), ("Two loops: ", True, NAVY), ("a speed drop is handled within a second; policy changes go through the safety check", False, GREY)],
    [("\u2022 ", True, BLUE), ("Privacy: ", True, NAVY), ("no payload or domain logging; the intent API is LAN-only and needs a token", False, GREY)],
], size=10)
for par in kf.text_frame.paragraphs:
    par.space_after = Pt(4)

# ---- Right column: AI layer ----
rx, rw = 8.05, 4.98
ah = box(s, rx, 0.9, rw, 0.36, PURPLE, shape=MSO_SHAPE.RECTANGLE)
text(ah, [[("Where we use ML, and how we check it helps", True, WHITE)]], size=10.5, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
ab = box(s, rx, 1.26, rw, 2.92, WHITE, line=PURPLE, shape=MSO_SHAPE.RECTANGLE)
text(ab, [
    [("1. Flow classifier: ", True, PURPLE), ("LightGBM on flow features with conformal prediction. A flow is prioritised only when the model is confident, "
      "which keeps wrong boosts under a target rate (say 1%). ", False, GREY), ("Compared with port-based rules.", True, NAVY)],
    [("2. Link model: ", True, PURPLE), ("trained offline on lab runs, it predicts how a policy change will affect call delay, "
      "so risky changes are dropped before the live trial. ", False, GREY), ("Measured by seconds of bad call delay avoided.", True, NAVY)],
    [("3. Auto-protect: ", True, PURPLE), ("when a call starts on a busy link it is protected automatically, within a daily per-device limit, "
      "and the user can undo it. ", False, GREY), ("Measured by time from call start to protection.", True, NAVY)],
    [("Each ML part is tested against the plain rule-based version. If it does not improve the numbers, we drop it.", False, GREY)],
], size=10.5)
for par in ab.text_frame.paragraphs:
    par.space_after = Pt(4)

eh = box(s, rx, 4.28, rw, 0.32, NAVY, shape=MSO_SHAPE.RECTANGLE)
text(eh, [[("Early test we ran (27 Oct)", True, YEL)]], size=10.5, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
eb = box(s, rx, 4.6, rw, 2.34, WHITE, line=NAVY, shape=MSO_SHAPE.RECTANGLE)

cd = CategoryChartData()
cd.categories = ["No QoS (FIFO)", "Class shaping (HTB)"]
cd.add_series("p95 call-probe delay (ms)", (138.0, 0.07))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(rx + 0.05), Inches(4.62), Inches(rw - 0.1), Inches(1.2), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "95th percentile ping delay during a download (ms)"
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
    [("Download speed was the same in both cases ", True, NAVY), ("(18.7 of 20 Mbps), so the call was protected without starving the download.", False, GREY)],
    [("Setup: 2 Linux namespaces, 20 Mbit link, 4 TCP streams, 50 pings/s, 5 runs each. No WAN delay was emulated. "
      "In Round 2 we will compare against CAKE, CAKE autorate and cake-autorate across 14 scenarios.", False, GREY)],
], size=9)

foot = s.shapes.add_textbox(Inches(0.3), Inches(7.0), Inches(12.73), Inches(0.4))
text(foot, [[("Scope: ", True, NAVY), ("the prototype runs in emulation. A real router would also need hardware offload handling, enough CPU for gigabit shaping, and Wi-Fi airtime fairness.", False, GREY)]],
     size=9, align=PP_ALIGN.CENTER)

notes = s.notes_slide.notes_text_frame
notes.text = (
    "Talking points (about 1 minute): "
    "In a home, calls, games, TVs and downloads share one link. The real problem is queueing delay, not bandwidth. "
    "We build on CAKE in Linux rather than replacing it. On top of it we add a rate loop that follows the link speed every second, "
    "a rule-based policy loop that goes through a safety check and can roll back, and a way for the user to protect a call for a set time. "
    "ML is used in three places: the flow classifier, a link model that screens policy changes, and auto-protect for calls. "
    "Each one is compared with the rule-based version and dropped if it does not help. "
    "Our early test: during a download, ping delay was 138 ms with no QoS and under 0.1 ms with class shaping, with the same download speed. "
    "In Round 2 we compare against CAKE and its autorate tools, not only against no QoS."
)

cp = p.core_properties
cp.title = "Team MM - Case Study 3 - PulseQoS"
cp.author = "Manas Girdhar"
cp.last_modified_by = "Meenakshi Satpathy"
cp.subject = "TELIPORT S4 Round 1 submission"
cp.keywords = ""
cp.comments = ""
p.save(out)
