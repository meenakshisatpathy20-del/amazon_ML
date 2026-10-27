# PulseQoS: design review, gaps and fixes (Round 1)

Reviewed: `Manas_PulseQoS_TELIPORT_S4.pdf` (the slide) and `PulseQoS_Design_Document.pdf` (18 pages).

**Overall:** the design is strong and honest. It builds on CAKE instead of reinventing it, keeps a deterministic baseline, separates the HTB and CAKE fairness claims correctly, and has a reproducible evaluation plan. The gaps below are what a networking judge could still catch. They are ordered by impact.

Facts were checked against the tc-cake(8) and tc-ctinfo(8) man pages (iproute2), RFC 8837 and the case-study PDF.

## A. Correctness gaps (fix before submitting)

| # | Gap | Why it matters | Fix |
|---|-----|----------------|-----|
| 1 | **Fast and slow control conflict.** The validator rejects any change made within the minimum hold time, and every change goes through a 10–30 s trial. A capacity cut is also a change. | In scenario S2 (100 → 20 Mbps), the shaper cut could be blocked or delayed by the anti-flap and trial rules, so the queue builds up. That is exactly the failure the case study names. | Split the control into **two loops**. **Fast loop (≤ 1 s):** the capacity estimator lowers the shaper rate directly. Rate *decreases* are exempt from the hold time and the trial; increases are slow and bounded. **Slow loop (10–30 s):** tin mappings, intents and HTB classes go through the safety gate. While the fast loop is changing the rate, the gate marks a running trial "inconclusive" instead of blaming the policy. |
| 2 | **Video calls in the Voice tin.** The design maps all Interactive-RT (calls) to Voice. | In CAKE diffserv4, Voice has a **25% threshold** (tc-cake(8)). At 20 Mbps that is 5 Mbps. A video call uses roughly 1–3 Mbps per direction, so two calls plus gaming can exceed it, and the excess loses priority. The lab's "50 pkt/s small packets" call is audio-only and would hide this. | Call **audio** and gaming go to Voice; call **video** goes to Video (50% threshold). This matches WebRTC's own marking guidance (RFC 8837: audio EF, video AF4x). Add a realistic video-call profile to the traffic generators, and test the case of 2 calls + gaming at 20 Mbps. |
| 3 | **Trusting inbound DSCP.** The design restores the mark via conntrack (correct), but doesn't say what happens to DSCP values that arrive from the Internet. | A remote sender can mark its traffic EF and jump into the Voice tin. tc-cake(8) itself warns that inbound markings often can't be trusted. | On the download path, overwrite DSCP from **our** conntrack mark (`tc action ctinfo dscp <mask> <statemask>`); flows with no mark are treated as best effort. Add `wash` on egress so internal markings don't leak to the ISP. Add one abuse test: an external flow marked EF. |
| 4 | **Who writes the conntrack mark is not specified.** `ctinfo` only *restores* a mark that something else stored. | Without this step, download classification silently doesn't work. | The classifier/controller writes the class into the flow's conntrack mark, using nftables `ct mark set …` rules or `conntrack -U … --mark` for a single flow. Upload: copy the class to DSCP (or to the skb mark with CAKE `fwmark`) before WAN CAKE. Download: `ctinfo` on the WAN ingress before redirecting to IFB. Week-1 test: confirm the mark survives NAT and the IFB redirect in both IPv4 and IPv6. |
| 5 | **RTT can't tell which direction is congested.** The capacity estimator uses RTT only. | When RTT rises, the controller doesn't know whether to cut upload or download, so it could throttle the wrong side. | Use **one-way delay**: ICMP timestamp probes (as `tsping` does, used by cake-autorate) or `irtt`, with RTT as a fallback. In the RTT fallback, cut only the direction whose achieved rate is near its shaper limit. Report per-direction estimation error. |

## B. Evaluation gaps (credibility)

| # | Gap | Fix |
|---|-----|-----|
| 6 | **Classifier trained on synthetic generators.** If training and testing traffic come from the same generator scripts, the model learns the generator, not the apps. The F1 score is inflated. | Train and test on **real application captures** recorded by the team with consent (calls, games, streaming, downloads), plus public labelled datasets where the licence allows (for example ISCX VPN-nonVPN 2016, CESNET-QUIC22; check each licence). Keep the generators for load only. Split by capture session. |
| 7 | **No time-to-classify metric.** Flows are Unknown (best effort) until classified, so the first seconds of a call aren't protected. | Report time-to-classify alongside F1, and test the scenario "download already running, call starts". |
| 8 | **No standard responsiveness metric.** | Add **RPM** (round-trips per minute under working conditions; the IETF responsiveness draft already in your sources) via the open-source `goresponsiveness` client. Judges recognise it, and it summarises bufferbloat in one number. |
| 9 | **Statistics.** Medians with 95% CIs are planned, but the analysis method isn't named. | Use paired runs (same seed per system pair), bootstrap CIs on the difference, and report effect size, not just p-values. |

## C. Security and privacy gaps

| # | Gap | Fix |
|---|-----|-----|
| 10 | **Intent API abuse.** Any LAN device could call "protect me" all day. The Fairness Budget limits duration, but nothing says who may ask. | API listens on LAN only; pairing or token per user; rate limit; owner can revoke; every intent is in the audit log. |
| 11 | **Household privacy.** A per-device "what are you doing" dashboard is sensitive inside a family or flat. | Store only class-level metadata, never domains or payload; short retention; per-device detail visible only to the account owner. |

## D. Wording and submission fixes

- The slide's architecture should show the **six layers the case study asks for**: device, edge, network, data, analytics and UI ("Expected Output": *architecture diagram showing device, edge, network, data, analytics and user-interface components*). The current diagram is a flow, not a layered view.
- ASUS row: "analyse packet content" is hard to defend. Better: "uses commercial signature-based app identification (DPI)".
- Verify the Maestro citation (venue and year) and the Round 2 dates (14 Nov–13 Dec) on the portal before quoting them.
- The slide has no evidence yet. The pilot below adds one real number.

## E. Pilot evidence (measured on 27 Oct 2026)

- **Purpose:** check that the problem (bufferbloat) and the fix (class shaping) show up in a real Linux kernel, not only in the design.
- **Setup:**
  - Two Linux network namespaces, 20 Mbit HTB bottleneck on the download direction.
  - "Call" = ICMP probes at 50 packets/s. "Download" = `iperf3` with 4 TCP streams.
  - 5 paired runs per system; latency measured during the loaded phase.

| System | p50 delay | p95 delay | p99 delay | Jitter | Download goodput |
|---|---|---|---|---|---|
| FIFO (1000-packet queue) | 110 ms | **138 ms** (range 128–152) | 153 ms | 8.5 ms | 18.7 Mbps |
| HTB class layout (call class first, bulk floor 2 Mbit) | 0.05 ms | **0.07 ms** | 0.10 ms | 0.01 ms | 18.7 Mbps |

**Limits (state them on the slide):**
- This is emulation, with no WAN delay. The container had no `netem`, `cake` or `fq_codel` modules.
- The probes are a call proxy, not a real call.
- Classification was ideal (matched by protocol).

It shows the mechanism, not PulseQoS's advantage over CAKE; that is the Round 2 question.

**Reproduce:**
```
sudo bash pulseqos/pilot/pilot.sh fifo 1 <outdir>
sudo bash pulseqos/pilot/pilot.sh htb 1 <outdir>
python3 pulseqos/pilot/analyze.py <outdir>
```
Needs `iproute2` and `iperf3`. The raw results are in `pulseqos/pilot/results/`.
