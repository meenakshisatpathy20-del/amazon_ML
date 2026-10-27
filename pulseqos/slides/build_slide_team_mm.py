"""Team MM, Case Study 3. Fills the official template without moving, resizing or restyling any template element.

All new shapes sit inside the template's own content area (Content Placeholder 2: 1.11in, 2.58in, 11.5 x 4.76in).
"""
import sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION

src, out = sys.argv[1], sys.argv[2]
p = Presentation(src)

BLUE = RGBColor(0x00, 0x8C, 0xC8)
NAVY = RGBColor(0x0B, 0x2E, 0x4F)
MID = RGBColor(0x2B, 0x6C, 0xB0)
YEL = RGBColor(0xF5, 0xB4, 0x00)
LANE = RGBColor(0xF2, 0xF8, 0xFC)
GREY = RGBColor(0x33, 0x33, 0x33)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xD9, 0x3A, 0x2B)
GREEN = RGBColor(0x1E, 0x8E, 0x3E)


def fill_text(shape, paras, size, color=GREY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, margins=0.05):
    """paras: list of paragraphs; each a list of (text, bold, color). Font family is left to the template theme."""
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margins)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, runs in enumerate(paras):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = align
        for t, b, c in runs:
            r = par.add_run()
            r.text = t
            r.font.size = Pt(size)
            r.font.bold = b
            r.font.color.rgb = c or color
    return tf


def rect(slide, x, y, w, h, fill, line=None, rounded=False):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
                               Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(0.75)
    s.shadow.inherit = False
    if rounded:
        s.adjustments[0] = 0.1
    return s


def arrow(slide, x1, y1, x2, y2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = NAVY
    c.line.width = Pt(1.25)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))


def node(slide, x, y, w, h, head, body, style="light", size=7.5):
    fill, line, hc, bc = {
        "light": (WHITE, BLUE, NAVY, GREY),
        "dark": (NAVY, None, YEL, WHITE),
        "ml": (MID, None, WHITE, WHITE),
    }[style]
    b = rect(slide, x, y, w, h, fill, line, rounded=True)
    paras = [[(head, True, hc)]] + ([[(body, False, bc)]] if body else [])
    fill_text(b, paras, size, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, margins=0.03)
    b.text_frame.paragraphs[0].runs[0].font.size = Pt(size + 0.5)
    return b


# ---------- Slide 1: only fill the existing text, nothing moved ----------
s1 = p.slides[0]
for sh in s1.shapes:
    if sh.has_text_frame and sh.text_frame.text.strip().startswith("Case Study No"):
        sh.text_frame.paragraphs[0].runs[0].text = "Case Study No. 3"
        sh.text_frame.word_wrap = False
    elif sh.is_placeholder and sh.placeholder_format.idx == 1:
        tf = sh.text_frame
        tf.text = "Team MM"
        tf.paragraphs[0].runs[0].font.bold = True
        for line in ["Manas Girdhar (Team Leader)", "Meenakshi Satpathy", "Birla Institute of Technology, Mesra"]:
            tf.add_paragraph().text = line

# ---------- Slide 2 ----------
s = p.slides[1]
title = body_ph = None
for sh in s.shapes:
    if sh.is_placeholder and sh.placeholder_format.idx == 0:
        title = sh
    elif sh.is_placeholder and sh.placeholder_format.idx == 1:
        body_ph = sh

# Title placeholder: text only, template position and style kept.
title.text_frame.text = "PulseQoS: Adaptive Home QoS"
sub = title.text_frame.add_paragraph()
r = sub.add_run()
r.text = "The call never notices the download. An adaptive QoS controller built on Linux tc and CAKE, with no payload inspection."
r.font.size = Pt(14)

# Content area from the template's own content placeholder.
CX, CY = Emu(body_ph.left).inches, Emu(body_ph.top).inches
CW, CH = Emu(body_ph.width).inches, Emu(body_ph.height).inches

# The placeholder itself carries the "Key design decisions" text, bottom-left, via text insets only.
LW = 6.95            # left column width
KH = 0.98            # height used by the key decisions text
tf = fill_text(body_ph, [
    [("Key design decisions", True, BLUE)],
    [("Tins: ", True, NAVY), ("call audio and games in Voice, call video in Video (Voice is capped at 25% in diffserv4).", False, GREY)],
    [("Trust: ", True, NAVY), ("DSCP from the Internet is cleared, so outside traffic cannot claim priority.", False, GREY)],
    [("Two loops: ", True, NAVY), ("a speed drop is handled within a second; policy changes pass a safety check first.", False, GREY)],
    [("Privacy: ", True, NAVY), ("no payload or domain logging; the intent API is LAN-only and needs a token.", False, GREY)],
], size=8.5, anchor=MSO_ANCHOR.BOTTOM)
tf.margin_left = Inches(0.08)
tf.margin_right = Inches(CW - LW + 0.08)
tf.margin_bottom = Inches(0.06)
for par in tf.paragraphs:
    par.level = 0
    par.space_before = Pt(0)
    par.space_after = Pt(1)
    pPr = par._p.get_or_add_pPr()
    pPr.set("marL", "0")
    pPr.set("indent", "0")
    for tag in ("buChar", "buAutoNum"):
        for el in pPr.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}" + tag):
            pPr.remove(el)
    pPr.insert(0, pPr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}buNone", {}))
# outline for the key-decisions block (drawn behind via z-order: added first after placeholder)
kd = rect(s, CX, CY + CH - KH, LW, KH, WHITE, BLUE)
s.shapes._spTree.remove(kd._element)
s.shapes._spTree.insert(2, kd._element)

# ---- Left: layered architecture ----
AY0 = CY
AH = CH - KH - 0.08
lanes = [("UI", 0.42), ("ANALYTICS\n& CONTROL", 0.92), ("DATA", 0.32), ("EDGE", 0.62), ("DEVICE &\nNETWORK", 0.42)]
gap = (AH - sum(h for _, h in lanes)) / (len(lanes) - 1)
LBW = 0.72
X0 = CX + LBW + 0.08
IW = LW - LBW - 0.12
ys = {}
y = AY0
for lab, h in lanes:
    rect(s, CX, y, LW, h, LANE)
    lb = rect(s, CX, y, LBW, h, BLUE)
    fill_text(lb, [[(l, True, WHITE)] for l in lab.split("\n")], 7, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, margins=0.02)
    ys[lab.split()[0]] = (y, h)
    y += h + gap

pad = 0.05
half = (IW - 0.1) / 2
y, h = ys["UI"]
node(s, X0, y + pad, half, h - 2 * pad, "Focus Mode app / REST API", "protect a call for N minutes; auto-protect has undo")
node(s, X0 + half + 0.1, y + pad, half, h - 2 * pad, "Dashboard", "latency, jitter, loss, queue depth, fairness, reason per change")

y, h = ys["ANALYTICS"]
q = (IW - 0.3) / 4
cols = [X0 + i * (q + 0.1) for i in range(4)]
node(s, cols[0], y + pad, q, h - 2 * pad, "Rate loop (1 s)", "estimates capacity from one-way delay; lowers shaper rate at once", "dark", 7)
node(s, cols[1], y + pad, q, h - 2 * pad, "Policy loop (10-30 s)", "rule-based, fixed set of actions, hysteresis and hold time", "dark", 7)
node(s, cols[2], y + pad, q, h - 2 * pad, "Link model (ML)", "predicts call delay per action; filters out risky ones", "ml", 7)
node(s, cols[3], y + pad, q, h - 2 * pad, "Safety check", "short live trial, keep or roll back; watchdog falls back to CAKE", "light", 7)
for i in range(3):
    arrow(s, cols[i] + q, y + h / 2, cols[i + 1], y + h / 2)

y, h = ys["DATA"]
node(s, X0, y + 0.04, IW, h - 0.08, "Flow table (conntrack), telemetry, versioned policies, audit log", "", size=7.5)

y, h = ys["EDGE"]
t3 = (IW - 0.2) / 3
ex = [X0 + i * (t3 + 0.1) for i in range(3)]
node(s, ex[0], y + pad, t3, h - 2 * pad, "Flow classifier (ML)", "packet sizes and timing only; unsure flows stay best effort", "ml", 7)
node(s, ex[1], y + pad, t3, h - 2 * pad, "Flow marking", "class kept in conntrack mark, restored with ctinfo", "light", 7)
node(s, ex[2], y + pad, t3, h - 2 * pad, "Linux tc", "CAKE on WAN and IFB; HTB variant for hard floors", "light", 7)
for i in range(2):
    arrow(s, ex[i] + t3, y + h / 2, ex[i + 1], y + h / 2)

y, h = ys["DEVICE"]
node(s, X0, y + pad, half, h - 2 * pad, "Home devices (emulated)", "laptop on a call, console, 3 TVs, a large download")
node(s, X0 + half + 0.1, y + pad, half, h - 2 * pad, "WAN link (emulated)", "netem + token bucket, 100 to 20 Mbps, IPv4 and IPv6")

# vertical hints
uy, uh = ys["UI"]; ay, ah = ys["ANALYTICS"]; ey, eh = ys["EDGE"]; dy, dh = ys["DEVICE"]
arrow(s, X0 + half / 2, uy + uh - pad, X0 + half / 2, ay + pad)
arrow(s, cols[3] + q / 2, ay + ah - pad, cols[3] + q / 2, ey + pad)
arrow(s, ex[0] + t3 / 2, dy + pad, ex[0] + t3 / 2, ey + eh - pad)
arrow(s, ex[2] + t3 / 2, ey + eh - pad, ex[2] + t3 / 2, dy + pad)

# ---- Right column ----
RX = CX + LW + 0.15
RW = CX + CW - RX
MLH = 2.2
mh = rect(s, RX, CY, RW, 0.28, MID)
fill_text(mh, [[("Where we use ML, and how we check it helps", True, WHITE)]], 9, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
mb = rect(s, RX, CY + 0.28, RW, MLH - 0.28, WHITE, MID)
fill_text(mb, [
    [("1. Flow classifier: ", True, MID), ("LightGBM with conformal prediction. A flow is prioritised only when the model is confident, "
      "keeping wrong boosts under a target rate (say 1%). ", False, GREY), ("Compared with port rules.", True, NAVY)],
    [("2. Link model: ", True, MID), ("trained offline on lab runs; predicts how a policy change affects call delay, so risky changes "
      "are dropped before the live trial. ", False, GREY), ("Measured by bad-delay seconds avoided.", True, NAVY)],
    [("3. Auto-protect: ", True, MID), ("a call starting on a busy link is protected automatically, within a daily per-device limit, "
      "with undo. ", False, GREY), ("Measured by time to protection.", True, NAVY)],
    [("Each ML part is tested against the rule-based version. If it does not improve the numbers, we drop it.", False, GREY)],
], 8.8)
for par in mb.text_frame.paragraphs:
    par.space_after = Pt(4)

PY0 = CY + MLH + 0.1
ph = rect(s, RX, PY0, RW, 0.28, NAVY)
fill_text(ph, [[("Early test we ran (27 Oct)", True, YEL)]], 9, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
pb = rect(s, RX, PY0 + 0.28, RW, CY + CH - PY0 - 0.28, WHITE, NAVY)

cd = CategoryChartData()
cd.categories = ["No QoS (FIFO)", "Class shaping (HTB)"]
cd.add_series("95th percentile ping delay (ms)", (138.0, 0.07))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(RX + 0.03), Inches(PY0 + 0.3), Inches(RW - 0.06), Inches(1.15), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "95th percentile ping delay during a download (ms)"
tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
tr.font.size = Pt(8.5); tr.font.bold = True; tr.font.color.rgb = NAVY
plot = ch.plots[0]
plot.gap_width = 50
plot.has_data_labels = True
dl = plot.data_labels
dl.font.size = Pt(9); dl.font.bold = True
dl.number_format = '#,##0.0#'; dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
for i, c in enumerate((RED, GREEN)):
    pt = plot.series[0].points[i]
    pt.format.fill.solid(); pt.format.fill.fore_color.rgb = c
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.maximum_scale = 240
ch.category_axis.tick_labels.font.size = Pt(8)
ch.category_axis.format.line.fill.background()

ev = s.shapes.add_textbox(Inches(RX + 0.03), Inches(PY0 + 1.45), Inches(RW - 0.06), Inches(CY + CH - PY0 - 1.47))
fill_text(ev, [
    [("Same download speed in both ", True, NAVY), ("(18.7 of 20 Mbps): the call was protected without starving the download.", False, GREY)],
    [("2 Linux namespaces, 20 Mbit link, 4 TCP streams, 50 pings/s, 5 runs each, no WAN delay. "
      "Round 2 compares against CAKE, CAKE autorate and cake-autorate in 14 scenarios.", False, GREY)],
], 7.5)

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
