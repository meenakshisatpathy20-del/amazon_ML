"""Run the full pipeline on the test set and write the two submission TSVs."""
import json
import sys
import time

import lightgbm as lgb
import numpy as np
import polars as pl

from common import attach_text, block, load_split
from features import FEATURES, add_features

WORK = sys.argv[1] if len(sys.argv) > 1 else "work"
OUT = sys.argv[2] if len(sys.argv) > 2 else "output"
meta = json.load(open(f"{WORK}/train_meta.json"))
THR = float(sys.argv[3]) if len(sys.argv) > 3 else meta["threshold"]
TOP_K = meta["top_k"]
t0 = time.time()

s1, q = load_split(WORK, "test")
pairs = pl.read_parquet(f"{WORK}/test_pairs.parquet")
print("blocked", pairs.height, f"{time.time()-t0:.0f}s", flush=True)

model = lgb.Booster(model_file=f"{WORK}/model.txt")
scored = []
CH = 300_000
for start in range(0, q.height, CH):
    part = pairs.filter((pl.col("iq") >= start) & (pl.col("iq") < start + CH))
    if part.height == 0:
        continue
    part = add_features(attach_text(part, s1, q))
    p = model.predict(part.select(FEATURES).to_numpy().astype(np.float32), num_threads=4)
    PF = ["n_tset", "a_tset", "c_ratio", "sk_ratio", "num_jac", "rel_n_tset", "rel_a_tset", "bscore", "brank", "aa_tset"]
    scored.append(part.select("iq", "i1", *PF).with_columns(pl.Series("p", p.astype(np.float32))))
    print(f"  scored queries<{start+CH}  {time.time()-t0:.0f}s", flush=True)
scored = pl.concat(scored)
scored.write_parquet(f"{WORK}/test_scored.parquet")

best = scored.sort(["p", "i1"], descending=[True, False]).group_by("iq").first()
acc = best.filter(pl.col("p") >= THR)
print("threshold", THR, "assigned queries", acc.height, "of", q.height, flush=True)

ids1 = s1.select("i1", "entity_id")
idq = q.select("iq", pl.col("entity_id").alias("qid"))


def lists(df, col):
    g = df.join(idq, on="iq").sort("qid").group_by("i1").agg(pl.col("qid").str.join(",").alias(col))
    return ids1.join(g, on="i1", how="left").with_columns(pl.col(col).fill_null("")) \
        .sort("i1").select(pl.col("entity_id").alias("source1_entity_id"), col)


import os
os.makedirs(OUT, exist_ok=True)
m = lists(acc, "matched_entity_ids")
m.write_csv(f"{OUT}/matching_results.tsv", separator="\t", quote_style="never")
del best
if not os.path.exists(f"{OUT}/candidate_pairs.tsv"):
    lists(scored.select("iq", "i1"), "candidate_entity_ids") \
        .write_csv(f"{OUT}/candidate_pairs.tsv", separator="\t", quote_style="never")
nm = (m["matched_entity_ids"] != "").sum()
print(f"S1 rows {m.height}, with matches {nm}, empty {m.height-nm}; "
      f"candidates/S1 {scored.height/s1.height:.2f}; done {time.time()-t0:.0f}s")
