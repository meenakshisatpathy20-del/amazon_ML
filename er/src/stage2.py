"""Stage 2: cluster-aware accept/reject of each record's best S1 candidate.

Stage 1 gives p(match) for every (S2/S3 record, S1 candidate) pair. Each record
is tentatively assigned to its best candidate; stage 2 then decides whether to
keep that assignment using context stage 1 cannot see:
  * margin to the record's runner-up candidate,
  * how many other records confidently chose the same S1 entity, and how
    strongly (a real business usually appears in several sources),
  * where this record ranks among the records that chose that S1.

Usage:
  python stage2.py train WORK RAW       # fit on out-of-fold stage-1 scores, tune threshold
  python stage2.py apply WORK OUT       # rewrite output/matching_results.tsv for test
"""
import json
import sys

import lightgbm as lgb
import numpy as np
import polars as pl

S2F = ["p1", "p2", "margin", "ncand_q", "o_n", "o_n50", "o_n90", "o_max", "o_mean",
       "o_sum", "rank_in_s", "in_n", "in_sum", "in_max_other", "p1_minus_omax",
       "an_n_tset", "an_c_ratio", "an_a_tset", "an_a_ratio", "an2_n_tset", "an2_a_tset",
       "an_best_n", "an_best_a", "q_is_s3", "q_nonascii", "same_src_anchor"]
S2F_BASE = S2F[:15]


def anchor_features(f: pl.DataFrame, qtext: pl.DataFrame) -> pl.DataFrame:
    """Compare each record with the two strongest OTHER records that chose the same S1."""
    from rapidfuzz import fuzz, process
    cp = lambda a, b, sc: process.cpdist(a, b, scorer=sc, workers=4, dtype=np.float32)
    ranked = f.select("iq", "i1", "p1").sort(["i1", "p1", "iq"], descending=[False, True, False]) \
        .with_columns(pl.int_range(pl.len()).over("i1").alias("_r"))
    tops = ranked.filter(pl.col("_r") < 3).select("i1", "_r", pl.col("iq").alias("aq"))
    # anchor 1/2 = best/second-best other record (skip self)
    j = ranked.select("iq", "i1", "_r").join(tops, on="i1", suffix="_a").filter(pl.col("_r") != pl.col("_r_a")) \
        .sort(["iq", "_r_a"]).with_columns(pl.int_range(pl.len()).over("iq").alias("k")).filter(pl.col("k") < 2)
    t = qtext.select("iq", "name", "core", "addr", "q_is_s3")
    j = j.join(t, on="iq").join(t.rename({"iq": "aq", "name": "a_name", "core": "a_core", "addr": "a_addr",
                                          "q_is_s3": "a_s3"}), on="aq")
    j = j.with_columns(
        pl.Series("n_tset", cp(j["name"].to_list(), j["a_name"].to_list(), fuzz.token_set_ratio)),
        pl.Series("c_ratio", cp(j["core"].to_list(), j["a_core"].to_list(), fuzz.ratio)),
        pl.Series("a_tset", cp(j["addr"].to_list(), j["a_addr"].to_list(), fuzz.token_set_ratio)),
        pl.Series("a_ratio", cp(j["addr"].to_list(), j["a_addr"].to_list(), fuzz.ratio)),
        (pl.col("q_is_s3") == pl.col("a_s3")).cast(pl.Float32).alias("same_src"))
    a1 = j.filter(pl.col("k") == 0).select("iq", pl.col("n_tset").alias("an_n_tset"),
                                            pl.col("c_ratio").alias("an_c_ratio"), pl.col("a_tset").alias("an_a_tset"),
                                            pl.col("a_ratio").alias("an_a_ratio"), pl.col("same_src").alias("same_src_anchor"))
    a2 = j.filter(pl.col("k") == 1).select("iq", pl.col("n_tset").alias("an2_n_tset"), pl.col("a_tset").alias("an2_a_tset"))
    f = f.join(a1, on="iq", how="left").join(a2, on="iq", how="left") \
        .join(qtext.select("iq", pl.col("q_is_s3").cast(pl.Float32), pl.col("name_nonascii").cast(pl.Float32).alias("q_nonascii")), on="iq")
    return f.with_columns(
        pl.max_horizontal("an_n_tset", "an2_n_tset").alias("an_best_n"),
        pl.max_horizontal("an_a_tset", "an2_a_tset").alias("an_best_a"))


def load_qtext(work, split):
    return pl.concat([
        pl.read_parquet(f"{work}/{split}_source2.parquet").with_columns(pl.lit(0, pl.Int8).alias("q_is_s3")),
        pl.read_parquet(f"{work}/{split}_source3.parquet").with_columns(pl.lit(1, pl.Int8).alias("q_is_s3")),
    ]).with_row_index("iq").select("iq", "name", "core", "addr", "q_is_s3", "name_nonascii")


def s2_features(scored: pl.DataFrame) -> pl.DataFrame:
    """scored: iq, i1, p for every candidate pair -> one row per query (its best S1)."""
    s = scored.sort(["iq", "p"], descending=[False, True])
    q = s.group_by("iq", maintain_order=True).agg(
        pl.col("i1").first(), pl.col("p").first().alias("p1"),
        pl.col("p").get(1, null_on_oob=True).fill_null(0.0).alias("p2"),
        pl.len().cast(pl.Float32).alias("ncand_q"))
    q = q.with_columns((pl.col("p1") - pl.col("p2")).alias("margin"))
    # other queries whose best is the same S1
    g = q.group_by("i1").agg(pl.len().alias("_n"), pl.col("p1").sum().alias("_sum"),
                             (pl.col("p1") >= 0.5).sum().alias("_n50"),
                             (pl.col("p1") >= 0.9).sum().alias("_n90"))
    q = q.join(g, on="i1").with_columns(
        (pl.col("_n") - 1).cast(pl.Float32).alias("o_n"),
        (pl.col("_n50") - (pl.col("p1") >= 0.5)).cast(pl.Float32).alias("o_n50"),
        (pl.col("_n90") - (pl.col("p1") >= 0.9)).cast(pl.Float32).alias("o_n90"),
        (pl.col("_sum") - pl.col("p1")).alias("o_sum"),
        pl.col("p1").rank("ordinal", descending=True).over("i1").cast(pl.Float32).alias("rank_in_s"),
    ).with_columns((pl.col("o_sum") / pl.col("o_n").clip(1)).alias("o_mean"))
    # max p1 among the OTHER queries choosing the same S1
    top2 = q.sort("p1", descending=True).group_by("i1").agg(
        pl.col("p1").first().alias("_m1"), pl.col("p1").get(1, null_on_oob=True).fill_null(0.0).alias("_m2"))
    q = q.join(top2, on="i1").with_columns(
        pl.when(pl.col("rank_in_s") == 1).then(pl.col("_m2")).otherwise(pl.col("_m1")).alias("o_max"))
    q = q.with_columns((pl.col("p1") - pl.col("o_max")).alias("p1_minus_omax"))
    # all candidate pairs pointing at that S1 (incoming evidence, any rank)
    inc = scored.group_by("i1").agg(pl.len().cast(pl.Float32).alias("in_n"),
                                    pl.col("p").sum().alias("in_sum"))
    q = q.join(inc, on="i1").with_columns(
        (pl.col("in_sum") - pl.col("p1")).alias("in_max_other"))
    return q.select("iq", "i1", *S2F_BASE)


PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_data_in_leaf=200,
              feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=1, verbose=-1,
              num_threads=4, seed=1)


def train(work, raw):
    from common import fbeta_macro
    oof = pl.read_parquet(f"{work}/oof.parquet")
    fold = oof.group_by("iq").agg(pl.col("fold").first())
    lab = oof.select("iq", "i1", "y")
    f = s2_features(oof.select("iq", "i1", "p"))
    f = anchor_features(f, load_qtext(work, "train")).join(fold, on="iq") \
        .join(lab, on=["iq", "i1"], how="left").with_columns(pl.col("y").fill_null(0))
    X = f.select(S2F).to_numpy().astype(np.float32)
    y, fo = f["y"].to_numpy(), f["fold"].to_numpy()
    pr = np.zeros(len(y), dtype=np.float32)
    for k in (0, 1):
        m = lgb.train(PARAMS, lgb.Dataset(X[fo != k], y[fo != k]), 500)
        pr[fo == k] = m.predict(X[fo == k])
    f = f.with_columns(pl.Series("p2s", pr))

    # rebuild the evaluation universe exactly as train.py did
    s1 = pl.read_parquet(f"{work}/train_source1.parquet").with_row_index("i1")
    rng = np.random.default_rng(0)
    A = s1.select("i1").filter(pl.Series(rng.random(s1.height) < 0.04))
    q = pl.concat([pl.read_parquet(f"{work}/train_source2.parquet").select("entity_id"),
                   pl.read_parquet(f"{work}/train_source3.parquet").select("entity_id")]).with_row_index("iq")
    gt = pl.read_csv(f"{raw}/train/train_ground_truth.tsv", separator="\t", quote_char=None,
                     infer_schema=False).with_columns(pl.col("matched_entity_ids").fill_null("").str.split(","))
    tp = gt.explode("matched_entity_ids").filter(pl.col("matched_entity_ids") != "") \
        .join(s1.select("i1", pl.col("entity_id").alias("source1_entity_id")), on="source1_entity_id") \
        .join(q.select("iq", pl.col("entity_id").alias("matched_entity_ids")), on="matched_entity_ids") \
        .select("iq", "i1").join(A, on="i1", how="semi")
    truth = {i: set() for i in A["i1"].to_list()}
    for a, b in tp.iter_rows():
        truth[b].add(a)
    fa = f.join(A, on="i1", how="semi")

    def score(col, t):
        pred = {}
        for a, b in fa.filter(pl.col(col) >= t).select("iq", "i1").iter_rows():
            pred.setdefault(b, set()).add(a)
        return fbeta_macro(pred, truth)

    base = {round(t, 3): score("p1", t) for t in (0.6, 0.65, 0.7)}
    print("stage-1 only:", base, flush=True)
    res = {}
    for t in np.arange(0.50, 0.931, 0.02):
        res[round(float(t), 3)] = score("p2s", t)
        print(f"  stage2 t={t:.3f} F0.5={res[round(float(t),3)]:.5f}", flush=True)
    bt = max(res, key=res.get)
    print("STAGE2 BEST", bt, res[bt], flush=True)
    # precision / recall report at the chosen threshold
    pred = {}
    for a, b in fa.filter(pl.col("p2s") >= bt).select("iq", "i1").iter_rows():
        pred.setdefault(b, set()).add(a)
    tp_n = sum(len(pred.get(s, set()) & t) for s, t in truth.items())
    pn = sum(len(v) for v in pred.values())
    tn = sum(len(t) for t in truth.values())
    mp, mr, ms = [], [], 0
    for s_, t in truth.items():
        pr_ = pred.get(s_, set())
        if not t and not pr_:
            mp.append(1.0); mr.append(1.0); ms += 1
            continue
        inter = len(pr_ & t)
        mp.append(inter / len(pr_) if pr_ else 0.0)
        mr.append(inter / len(t) if t else 0.0)
    rep = {"macro_f05": res[bt], "macro_precision": float(np.mean(mp)), "macro_recall": float(np.mean(mr)),
           "pair_precision": tp_n / pn, "pair_recall": tp_n / tn, "threshold": bt,
           "eval_s1_entities": len(truth), "true_pairs": tn, "predicted_pairs": pn, "correct_pairs": tp_n,
           "singletons_correct": ms, "singletons_total": sum(1 for t in truth.values() if not t)}
    print("REPORT", json.dumps(rep, indent=1), flush=True)
    json.dump(rep, open(f"{work}/eval_report.json", "w"), indent=1)
    m = lgb.train(PARAMS, lgb.Dataset(X, y), 500)
    m.save_model(f"{work}/model_s2.txt")
    json.dump({"threshold": bt, "f05": res[bt], "stage1": base}, open(f"{work}/stage2_meta.json", "w"))


def apply(work, out):
    meta = json.load(open(f"{work}/stage2_meta.json"))
    scored = pl.read_parquet(f"{work}/test_scored.parquet")
    f = anchor_features(s2_features(scored), load_qtext(work, "test"))
    m = lgb.Booster(model_file=f"{work}/model_s2.txt")
    f = f.with_columns(pl.Series("p2s", m.predict(f.select(S2F).to_numpy().astype(np.float32))))
    acc = f.filter(pl.col("p2s") >= meta["threshold"]).select("iq", "i1")
    s1 = pl.read_parquet(f"{work}/test_source1.parquet").with_row_index("i1").select("i1", "entity_id")
    q = pl.concat([pl.read_parquet(f"{work}/test_source2.parquet").select("entity_id"),
                   pl.read_parquet(f"{work}/test_source3.parquet").select("entity_id")]) \
        .with_row_index("iq").rename({"entity_id": "qid"})
    g = acc.join(q, on="iq").sort("qid").group_by("i1").agg(pl.col("qid").str.join(",").alias("matched_entity_ids"))
    res = s1.join(g, on="i1", how="left").with_columns(pl.col("matched_entity_ids").fill_null("")) \
        .sort("i1").select(pl.col("entity_id").alias("source1_entity_id"), "matched_entity_ids")
    res.write_csv(f"{out}/matching_results.tsv", separator="\t", quote_style="never")
    print("stage2 applied: assigned", acc.height, "records; S1 with matches",
          (res["matched_entity_ids"] != "").sum(), "of", res.height)


if __name__ == "__main__":
    if sys.argv[1] == "train":
        train(sys.argv[2], sys.argv[3])
    else:
        apply(sys.argv[2], sys.argv[3])
