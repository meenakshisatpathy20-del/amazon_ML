#!/bin/bash
# Feasibility pilot: FIFO (bufferbloat) vs HTB priority layout, 20 Mbit bottleneck.
# "Call" = 50 pkt/s ICMP probes (proxy); "bulk" = iperf3 TCP download-direction flow.
# Usage: pilot.sh <mode: fifo|htb> <run_id> <outdir>
set -e
MODE=$1; RUN=$2; OUT=$3
RATE=20mbit
cleanup() { ip netns del home 2>/dev/null || true; ip netns del isp 2>/dev/null || true; }
cleanup; trap cleanup EXIT
ip netns add home; ip netns add isp
ip link add vh netns home type veth peer name vi netns isp
ip -n home addr add 10.0.0.2/24 dev vh; ip -n isp addr add 10.0.0.1/24 dev vi
for n in home isp; do ip -n $n link set lo up; done
ip -n home link set vh up; ip -n isp link set vi up

# Bottleneck on the ISP->home direction (download), like a home WAN link.
if [ "$MODE" = fifo ]; then
  ip netns exec isp tc qdisc add dev vi root handle 1: htb default 10
  ip netns exec isp tc class add dev vi parent 1: classid 1:10 htb rate $RATE ceil $RATE
  ip netns exec isp tc qdisc add dev vi parent 1:10 pfifo limit 1000
else
  ip netns exec isp tc qdisc add dev vi root handle 1: htb default 30
  ip netns exec isp tc class add dev vi parent 1: classid 1:1 htb rate $RATE ceil $RATE
  # interactive: small guaranteed rate, top priority, short queue
  ip netns exec isp tc class add dev vi parent 1:1 classid 1:10 htb rate 2mbit ceil $RATE prio 0
  # bulk: floor of 10% (2 Mbit) so it is never starved
  ip netns exec isp tc class add dev vi parent 1:1 classid 1:30 htb rate 2mbit ceil $RATE prio 1
  ip netns exec isp tc qdisc add dev vi parent 1:10 pfifo limit 50
  ip netns exec isp tc qdisc add dev vi parent 1:30 pfifo limit 1000
  ip netns exec isp tc filter add dev vi parent 1: protocol ip prio 1 u32 match ip protocol 1 0xff flowid 1:10
fi

ip netns exec isp iperf3 -s -D -1 >/dev/null
sleep 0.5
# Idle phase 5 s, then bulk download (server -> client, -R) for 20 s, probes throughout.
ip netns exec home ping -i 0.02 -w 27 -D 10.0.0.1 > "$OUT/${MODE}_${RUN}_ping.txt" &
PP=$!
sleep 5
ip netns exec home iperf3 -c 10.0.0.1 -R -P 4 -t 20 -J > "$OUT/${MODE}_${RUN}_iperf.json" || true
wait $PP || true
