"""Stage 1: candidate generation for a split -> work/<split>_pairs.parquet"""
import sys, time
import polars as pl
from common import block, load_split

WORK, SPLIT, TOP_K = sys.argv[1], sys.argv[2], int(sys.argv[3])
t0 = time.time()
s1, q = load_split(WORK, SPLIT)
pairs = block(s1, q, TOP_K, out_dir=f"{WORK}/{SPLIT}_pairs_parts")
pairs.write_parquet(f"{WORK}/{SPLIT}_pairs.parquet")
print(f"{SPLIT}: pairs={pairs.height} per-query={pairs.height/q.height:.2f} "
      f"per-S1={pairs.height/s1.height:.2f} time={time.time()-t0:.0f}s", flush=True)
