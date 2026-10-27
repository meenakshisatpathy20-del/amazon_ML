import json, re, sys, glob, os, statistics as st

d = sys.argv[1]


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


res = {}
for m in ("fifo", "htb"):
    rows = []
    for pf in sorted(glob.glob(os.path.join(d, f"{m}_*_ping.txt"))):
        run = pf.split("_")[-2]
        pts = [(float(a), float(b)) for a, b in re.findall(r"\[(\d+\.\d+)\].*time=([\d.]+)", open(pf).read())]
        t0 = pts[0][0]
        idle = [r for t, r in pts if t - t0 < 4.5]
        load = [r for t, r in pts if 7 <= t - t0 <= 24]  # skip slow-start, stop before iperf ends
        sent = len(re.findall(r"icmp_seq", open(pf).read()))
        j = json.load(open(os.path.join(d, f"{m}_{run}_iperf.json")))
        gp = j["end"]["sum_received"]["bits_per_second"] / 1e6
        jit = st.mean(abs(a - b) for a, b in zip(load, load[1:]))
        rows.append(dict(idle_p50=pct(idle, 50), p50=pct(load, 50), p95=pct(load, 95), p99=pct(load, 99),
                         jitter=jit, goodput=gp))
    res[m] = rows
    print(m, "runs", len(rows))
    for k in rows[0]:
        v = [r[k] for r in rows]
        print(f"  {k:9s} median {st.median(v):8.3f}  min {min(v):8.3f}  max {max(v):8.3f}")
json.dump(res, open(os.path.join(d, "summary.json"), "w"), indent=1)
