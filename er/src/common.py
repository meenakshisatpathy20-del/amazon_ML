import numpy as np
import polars as pl

from blocking import build_index, candidates
from features import add_features


def load_split(work, split):
    s1 = pl.read_parquet(f"{work}/{split}_source1.parquet")
    s2 = pl.read_parquet(f"{work}/{split}_source2.parquet").with_columns(pl.lit(0, pl.Int8).alias("q_is_s3"))
    s3 = pl.read_parquet(f"{work}/{split}_source3.parquet").with_columns(pl.lit(1, pl.Int8).alias("q_is_s3"))
    s1 = s1.with_row_index("i1").with_columns(
        pl.len().over(["country", "core"]).alias("s_name_freq"))
    q = pl.concat([s2, s3]).with_row_index("iq")
    return s1, q


def block(s1, q, top_k, out_dir=None):
    dfc, post = build_index(s1)
    return candidates(q, dfc, post, top_k=top_k, out_dir=out_dir)


def attach_text(pairs, s1, q):
    s1c = s1.select("i1", pl.col("name").alias("s_name"), pl.col("core").alias("s_core"),
                    pl.col("addr").alias("s_addr"), pl.col("squash").alias("s_squash"),
                    "s_name_freq")
    qc = q.select("iq", pl.col("name").alias("q_name"), pl.col("core").alias("q_core"),
                  pl.col("addr").alias("q_addr"), pl.col("squash").alias("q_squash"),
                  pl.col("name_nonascii").alias("q_nonascii"), "q_is_s3")
    return pairs.join(qc, on="iq").join(s1c, on="i1")


def fbeta_macro(pred: dict, truth: dict, beta=0.5):
    b2 = beta * beta
    tot = 0.0
    for s, t in truth.items():
        p = pred.get(s, set())
        if not p and not t:
            tot += 1
            continue
        if not p or not t:
            continue
        tp = len(p & t)
        if tp == 0:
            continue
        pr, rc = tp / len(p), tp / len(t)
        tot += (1 + b2) * pr * rc / (b2 * pr + rc)
    return tot / len(truth)
