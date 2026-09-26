"""Pairwise similarity features for (query S2/S3 record, candidate S1 record)."""
import numpy as np
import polars as pl
from rapidfuzz import fuzz, process
from rapidfuzz.distance import JaroWinkler

W = 4  # rapidfuzz worker threads

FEATURES = [
    "bscore", "bshared", "brank", "bratio", "bgap", "ncand",
    "n_tset", "n_tsort", "n_ratio", "n_partial", "n_jw", "c_tset", "c_ratio",
    "c_partial", "sq_ratio", "sq_partial",
    "a_tset", "a_ratio", "a_partial", "a_tsort",
    "num_jac", "num_inter", "num_first_eq", "q_num_n", "s_num_n",
    "q_addr_empty", "s_addr_empty", "q_nonascii", "q_is_s3",
    "q_core_len", "s_core_len", "core_len_ratio", "s_name_freq", "tok_jac",
]


def _cp(a, b, scorer):
    return process.cpdist(a, b, scorer=scorer, workers=W, dtype=np.float32)


def add_features(p: pl.DataFrame) -> pl.DataFrame:
    """p has pair columns: bscore,bshared,iq and q_*/s_* text columns."""
    p = p.with_columns(
        pl.col("bscore").rank("ordinal", descending=True).over("iq").cast(pl.Float32).alias("brank"),
        (pl.col("bscore") / pl.col("bscore").max().over("iq")).alias("bratio"),
        (pl.col("bscore") - pl.col("bscore").max().over("iq")).alias("bgap"),
        pl.len().over("iq").cast(pl.Float32).alias("ncand"),
    )
    qn, sn = p["q_name"].to_list(), p["s_name"].to_list()
    qc, sc = p["q_core"].to_list(), p["s_core"].to_list()
    qa, sa = p["q_addr"].to_list(), p["s_addr"].to_list()
    qs, ss = p["q_squash"].to_list(), p["s_squash"].to_list()
    cols = {
        "n_tset": _cp(qn, sn, fuzz.token_set_ratio),
        "n_tsort": _cp(qn, sn, fuzz.token_sort_ratio),
        "n_ratio": _cp(qn, sn, fuzz.ratio),
        "n_partial": _cp(qn, sn, fuzz.partial_ratio),
        "n_jw": _cp(qc, sc, JaroWinkler.normalized_similarity),
        "c_tset": _cp(qc, sc, fuzz.token_set_ratio),
        "c_ratio": _cp(qc, sc, fuzz.ratio),
        "c_partial": _cp(qc, sc, fuzz.partial_ratio),
        "sq_ratio": _cp(qs, ss, fuzz.ratio),
        "sq_partial": _cp(qs, ss, fuzz.partial_ratio),
        "a_tset": _cp(qa, sa, fuzz.token_set_ratio),
        "a_ratio": _cp(qa, sa, fuzz.ratio),
        "a_partial": _cp(qa, sa, fuzz.partial_ratio),
        "a_tsort": _cp(qa, sa, fuzz.token_sort_ratio),
    }
    p = p.with_columns([pl.Series(k, v) for k, v in cols.items()])
    qnum = pl.col("q_addr").str.extract_all(r"\d+").list.unique()
    snum = pl.col("s_addr").str.extract_all(r"\d+").list.unique()
    qtok = pl.col("q_core").str.split(" ").list.unique()
    stok = pl.col("s_core").str.split(" ").list.unique()
    p = p.with_columns(
        qnum.alias("_qn"), snum.alias("_sn"), qtok.alias("_qt"), stok.alias("_st"),
    ).with_columns(
        pl.col("_qn").list.set_intersection("_sn").list.len().cast(pl.Float32).alias("num_inter"),
        pl.col("_qn").list.set_union("_sn").list.len().cast(pl.Float32).alias("_nu"),
        (pl.col("q_addr").str.extract(r"(\d+)") == pl.col("s_addr").str.extract(r"(\d+)"))
        .fill_null(False).cast(pl.Float32).alias("num_first_eq"),
        pl.col("_qn").list.len().cast(pl.Float32).alias("q_num_n"),
        pl.col("_sn").list.len().cast(pl.Float32).alias("s_num_n"),
        (pl.col("q_addr") == "").cast(pl.Float32).alias("q_addr_empty"),
        (pl.col("s_addr") == "").cast(pl.Float32).alias("s_addr_empty"),
        pl.col("q_nonascii").cast(pl.Float32),
        pl.col("q_is_s3").cast(pl.Float32),
        pl.col("q_core").str.len_chars().cast(pl.Float32).alias("q_core_len"),
        pl.col("s_core").str.len_chars().cast(pl.Float32).alias("s_core_len"),
        (pl.col("_qt").list.set_intersection("_st").list.len()
         / pl.col("_qt").list.set_union("_st").list.len().clip(1)).cast(pl.Float32).alias("tok_jac"),
        pl.col("s_name_freq").cast(pl.Float32),
        pl.col("bshared").cast(pl.Float32),
        pl.col("bscore").cast(pl.Float32),
    ).with_columns(
        (pl.col("num_inter") / pl.col("_nu").clip(1)).alias("num_jac"),
        (pl.min_horizontal("q_core_len", "s_core_len")
         / pl.max_horizontal("q_core_len", "s_core_len").clip(1)).alias("core_len_ratio"),
    )
    return p
