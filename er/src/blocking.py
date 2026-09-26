"""Candidate generation: inverted index over PAIRS of tokens.

Single tokens are heavily reused in this data (hundreds of S1 records share
"apex", "108" or "richardson"), but pairs of tokens from the same record
(name x name, name x address, address x address) are highly selective.

For every record we take its RAREST `TOKS` tokens (by S1 document frequency),
form all unordered pairs, and hash them together with the record's country
label (an open set of strings, nothing is hard-coded). A Source-2/3 query is
compared with every Source-1 record that shares at least one rare pair key; the
candidates are ranked by the summed IDF of the shared pair keys, and the top-K
are kept.
"""
import polars as pl

TOKS = 9             # rarest tokens per record used to form pair keys
MAX_PAIR_DF = 60     # pair keys shared by more S1 records than this are dropped
TOP_K = 8            # candidates kept per query


def single_tokens(df: pl.DataFrame, idx_col: str) -> pl.DataFrame:
    name = df.select(idx_col, "country", pl.col("core").str.split(" ").alias("t")) \
        .explode("t").filter(pl.col("t").str.len_chars() >= 2) \
        .with_columns(("n" + pl.col("t")).alias("t"))
    addr = df.select(idx_col, "country", pl.col("addr").str.split(" ").alias("t")) \
        .explode("t").filter(pl.col("t").str.len_chars() >= 1) \
        .with_columns(("a" + pl.col("t")).alias("t"))
    sq = df.select(idx_col, "country", ("q" + pl.col("squash")).alias("t")) \
        .filter(pl.col("t").str.len_chars() >= 7)
    out = pl.concat([name, addr, sq])
    return out.select(idx_col, (pl.col("country") + "|" + pl.col("t")).hash().alias("h")).unique()


def pair_keys(tok: pl.DataFrame, idx_col: str, tdf: pl.DataFrame) -> pl.DataFrame:
    """Keep each record's rarest TOKS tokens and emit hashed unordered pairs."""
    t = tok.join(tdf, on="h") \
        .sort([idx_col, "df", "h"]).group_by(idx_col, maintain_order=True).head(TOKS) \
        .with_columns(pl.int_range(pl.len()).over(idx_col).alias("pos")).select(idx_col, "h", "pos")
    a = t.join(t, on=idx_col, suffix="_b").filter(pl.col("pos") < pl.col("pos_b"))
    lo = pl.min_horizontal("h", "h_b")
    hi = pl.max_horizontal("h", "h_b")
    return a.select(idx_col, pl.struct(lo.alias("a"), hi.alias("b")).hash().alias("k"))


def build_index(s1: pl.DataFrame, chunk: int = 400_000):
    t1 = single_tokens(s1, "i1")
    tdf = t1.group_by("h").agg(pl.len().alias("df"))
    parts = []
    for start in range(0, s1.height, chunk):
        ids = s1["i1"].slice(start, chunk)
        parts.append(pair_keys(t1.filter(pl.col("i1").is_in(ids.implode())), "i1", tdf))
    pk = pl.concat(parts)
    kdf = pk.group_by("k").agg(pl.len().alias("kdf"))
    n1 = s1.height
    kdf = kdf.filter(pl.col("kdf") <= MAX_PAIR_DF).with_columns(
        (pl.lit(n1) / pl.col("kdf")).log().cast(pl.Float32).alias("w"))
    post = pk.join(kdf.select("k", "w"), on="k")
    return tdf, post


def candidates(q: pl.DataFrame, tdf: pl.DataFrame, post: pl.DataFrame,
               top_k: int = TOP_K, chunk: int = 200_000) -> pl.DataFrame:
    """q must have columns iq, country, core, addr, squash."""
    outs = []
    for start in range(0, q.height, chunk):
        part = q.slice(start, chunk)
        pk = pair_keys(single_tokens(part, "iq"), "iq", tdf).unique()
        pairs = pk.join(post, on="k") \
            .group_by(["iq", "i1"]).agg(pl.col("w").sum().alias("bscore"),
                                        pl.len().alias("bshared"))
        pairs = pairs.sort(["iq", "bscore", "i1"], descending=[False, True, False]) \
            .group_by("iq", maintain_order=True).head(top_k)
        outs.append(pairs)
        if (start // chunk) % 10 == 0:
            print(f"  block {start + part.height}/{q.height} pairs={sum(o.height for o in outs)}",
                  flush=True)
    return pl.concat(outs)
