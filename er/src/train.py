"""Train the pairwise matcher on a held-out-by-entity sample of the training set.

1. Block ALL train S2/S3 records against ALL train S1 (same as test time).
2. Pick a random 12% of S1 entities (eval universe A). Use every query that
   either truly belongs to A or has a candidate in A (so false merges from
   other records onto A are counted exactly as in the real setting).
3. Split A into 2 folds by S1 entity; train LightGBM on one, predict the other
   (out-of-fold), tune the decision threshold on OOF macro F0.5.
"""
import json
import sys
import os
import time

import lightgbm as lgb
import numpy as np
import polars as pl

from common import attach_text, block, fbeta_macro, load_split
from features import FEATURES, add_features

WORK = sys.argv[1] if len(sys.argv) > 1 else "work"
RAW = sys.argv[2] if len(sys.argv) > 2 else "../data/raw"
TOP_K = int(sys.argv[3]) if len(sys.argv) > 3 else 8
FRAC = 0.05
SPLIT = os.environ.get("SPLIT", "train")
t0 = time.time()

s1, q = load_split(WORK, SPLIT)
gt = pl.read_csv(f"{RAW}/train/train_ground_truth.tsv", separator="\t", quote_char=None,
                 infer_schema=False)
gt = gt.with_columns(pl.col("matched_entity_ids").fill_null("").str.split(","))
truth_pairs = gt.explode("matched_entity_ids").filter(pl.col("matched_entity_ids") != "") \
    .rename({"source1_entity_id": "s1_id", "matched_entity_ids": "q_id"})
id1 = s1.select("i1", pl.col("entity_id").alias("s1_id"))
idq = q.select("iq", pl.col("entity_id").alias("q_id"))
truth_pairs = truth_pairs.join(id1, on="s1_id").join(idq, on="q_id").select("iq", "i1")
print("truth pairs", truth_pairs.height, f"{time.time()-t0:.0f}s", flush=True)

pairs = pl.read_parquet(f"{WORK}/{SPLIT}_pairs.parquet")
print("blocked", pairs.height, f"{time.time()-t0:.0f}s", flush=True)

# blocking recall on all train
hit = truth_pairs.join(pairs.select("iq", "i1"), on=["iq", "i1"], how="semi").height
print(f"BLOCKING recall(all train)={hit/truth_pairs.height:.4f} "
      f"pairs/query={pairs.height/q.height:.2f} pairs/S1={pairs.height/s1.height:.2f}", flush=True)

rng = np.random.default_rng(0)
A = s1.select("i1").filter(pl.Series(rng.random(s1.height) < FRAC))
A = A.with_columns(pl.Series("fold", rng.integers(0, 2, A.height)))
qa = pl.concat([truth_pairs.join(A, on="i1", how="semi").select("iq"),
                pairs.with_columns(pl.col("bscore").rank("ordinal", descending=True).over("iq").alias("_r"))
                .filter(pl.col("_r") <= 3).join(A, on="i1", how="semi").select("iq")]).unique()
sub = pairs.join(qa, on="iq", how="semi")
sub = sub.join(truth_pairs.with_columns(pl.lit(1, pl.Int8).alias("y")), on=["iq", "i1"], how="left") \
    .with_columns(pl.col("y").fill_null(0))
# fold of a query = fold of its true S1 if in A, else fold of its best candidate in A
qfold = truth_pairs.join(A, on="i1").select("iq", "fold")
qfold2 = sub.join(A, on="i1").sort("bscore", descending=True).group_by("iq").first().select("iq", "fold")
qfold = pl.concat([qfold, qfold2.join(qfold, on="iq", how="anti")])
sub = sub.join(qfold, on="iq")
print("train pairs", sub.height, "queries", qa.height, "pos", sub["y"].sum(), f"{time.time()-t0:.0f}s", flush=True)
# features in 8 batches of whole queries (bounded memory)
sub = pl.concat([add_features(attach_text(c, s1, q)).drop(["_qn", "_sn", "_qt", "_st", "_nu", "q_core", "s_core", "q_squash", "s_squash"]) for c in
                 [sub.filter(pl.col("iq") % 8 == k) for k in range(8)]])
print("features done", f"{time.time()-t0:.0f}s", flush=True)

params = dict(objective="binary", learning_rate=0.06, num_leaves=127, min_data_in_leaf=100,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
              verbose=-1, num_threads=4, seed=0)
X = sub.select(FEATURES).to_numpy().astype(np.float32)
y = sub["y"].to_numpy()
fold = sub["fold"].to_numpy()
PF = ["n_tset", "a_tset", "c_ratio", "sk_ratio", "num_jac", "rel_n_tset", "rel_a_tset", "bscore", "brank", "aa_tset", "hn_logdiff", "hn_small_off", "hn_trunc", "hn_same", "extra_q_tok"]
sub = sub.select("iq", "i1", "y", "fold", "q_name", "q_addr", "s_name", "s_addr", *PF)
import gc; gc.collect()
oof = np.zeros(len(y), dtype=np.float32)
for f in (0, 1):
    tr, va = fold != f, fold == f
    m = lgb.train(params, lgb.Dataset(X[tr], y[tr]), num_boost_round=600)
    oof[va] = m.predict(X[va])
    print(f"fold {f} done {time.time()-t0:.0f}s", flush=True)

sub = sub.with_columns(pl.Series("p", oof))
# assignment: each query -> its single best S1 candidate
best = sub.sort("p", descending=True).group_by("iq").first().select("iq", "i1", "p")
Aset = set(A["i1"].to_list())
truth = {i: set() for i in Aset}
for iq_, i1_ in truth_pairs.join(A, on="i1", how="semi").iter_rows():
    truth[i1_].add(iq_)
best_in_A = best.join(A, on="i1", how="semi")
res = {}
for t in np.arange(0.30, 0.96, 0.025):
    pred = {}
    for iq_, i1_ in best_in_A.filter(pl.col("p") >= t).select("iq", "i1").iter_rows():
        pred.setdefault(i1_, set()).add(iq_)
    res[round(float(t), 3)] = fbeta_macro(pred, truth)
    print(f"  t={t:.3f} OOF macroF0.5={res[round(float(t),3)]:.5f}", flush=True)
bt = max(res, key=res.get)
print("BEST threshold", bt, "OOF F0.5", res[bt], flush=True)

# final model on all sampled pairs
m = lgb.train(params, lgb.Dataset(X, y), num_boost_round=600)
m.save_model(f"{WORK}/model.txt")
imp = sorted(zip(FEATURES, m.feature_importance("gain")), key=lambda x: -x[1])
print("importance", [(a, int(b)) for a, b in imp[:15]])
json.dump({"threshold": bt, "oof": res, "top_k": TOP_K, "split": SPLIT, "frac": FRAC}, open(f"{WORK}/train_meta.json", "w"), indent=1)
sub.select("iq", "i1", "y", "p", "fold", "q_name", "q_addr", "s_name", "s_addr", *PF) \
    .write_parquet(f"{WORK}/oof.parquet")
print("done", f"{time.time()-t0:.0f}s")
