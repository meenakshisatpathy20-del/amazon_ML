"""Normalize names/addresses of every source file and write parquet.

Country-agnostic: transliterate any script to ASCII (unidecode), lowercase,
canonicalize common legal/street abbreviations for US, India and French text.
"""
import re
import sys
from pathlib import Path

import polars as pl
from unidecode import unidecode

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
WORK = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("work")
WORK.mkdir(parents=True, exist_ok=True)

# legal / filler words: removed from the "core" name (still kept in full name)
LEGAL = {
    "llc", "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "pvt", "private", "lp", "llp", "plc", "pllc", "pc", "sa", "sas",
    "sarl", "eurl", "sci", "sasu", "snc", "the", "and", "of", "dba", "d", "b", "a",
    "group", "services", "service", "center", "centre", "partners", "holdings",
    "enterprises", "company", "cie", "et", "de", "du", "des", "la", "le", "les",
    "id", "prvt", "praivet", "privet", "limted", "pvt", "praibhet", "prayvet", "pte", "l", "c", "i", "n", "s", "e", "com", "www", "net", "org",
}

STREET = {
    "street": "st", "road": "rd", "drive": "dr", "avenue": "ave", "av": "ave",
    "lane": "ln", "court": "ct", "circle": "cir", "boulevard": "blvd", "bd": "blvd",
    "bld": "blvd", "place": "pl", "trail": "trl", "parkway": "pkwy",
    "highway": "hwy", "terrace": "ter", "square": "sq", "north": "n",
    "south": "s", "east": "e", "west": "w", "apartment": "apt", "suite": "ste",
    "r": "rue", "floor": "flr", "fl": "flr", "nagar": "ngr", "sector": "sec",
    "mount": "mt", "saint": "st", "sainte": "ste", "point": "pt", "way": "wy",
    "center": "ctr", "centre": "ctr", "allee": "all", "impasse": "imp",
    "chemin": "ch", "route": "rte", "keralam": "kerala", "calcutta": "kolkata",
    "bangalore": "bengaluru", "bombay": "mumbai", "madras": "chennai",
    "second": "2nd", "first": "1st", "third": "3rd", "ground": "grd",
}
US_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
    "florida": "fl", "georgia": "ga", "hawaii": "hi", "idaho": "id",
    "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn",
    "mississippi": "ms", "missouri": "mo", "montana": "mt", "nebraska": "ne",
    "nevada": "nv", "new hampshire": "nh", "new jersey": "nj",
    "new mexico": "nm", "new york": "ny", "north carolina": "nc",
    "north dakota": "nd", "ohio": "oh", "oklahoma": "ok", "oregon": "or",
    "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
    "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut",
    "vermont": "vt", "virginia": "va", "washington": "wa",
    "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy",
    "district of columbia": "dc",
}
ADDR_DROP = {"none", "null", "na", "n/a", "no", "hno", "h", "door", "unit",
             "pmb", "po", "box", "shop", "shp", "plot", "#"}

_non_alnum = re.compile(r"[^a-z0-9 ]+")
_space = re.compile(r"\s+")
_rep = re.compile(r"(.)\1+")
_leet = str.maketrans({"1": "l", "0": "o", "3": "e", "5": "s", "4": "a", "7": "t"})
_state_re = re.compile(r"\b(" + "|".join(sorted(US_STATES, key=len, reverse=True)) + r")\b")


def ascii_lower(s: str) -> str:
    if s is None:
        return ""
    if not s.isascii():
        s = unidecode(s)
    return s.lower()


def norm_name(s: str) -> str:
    s = ascii_lower(s)
    s = s.replace("&", " and ").replace("+", " and ")
    s = re.sub(r"\.(com|net|org|in|fr|co)\b", " ", s)
    s = s.replace("@", " ").replace("'", "")
    s = re.sub(r"\(id: ?\d+\)", " ", s)
    s = _non_alnum.sub(" ", s)
    toks = []
    for t in s.split():
        if any(c.isalpha() for c in t) and any(c.isdigit() for c in t):
            t = t.translate(_leet)          # p1atinum -> platinum
        toks.append(_rep.sub(r"\1", t))   # investtmentt -> investment
    return " ".join(toks)


def norm_addr(s: str) -> str:
    s = ascii_lower(s)
    if s in ("", "none", "null", "nan"):
        return ""
    s = _state_re.sub(lambda m: US_STATES[m.group(1)], s)
    s = s.replace("h.no", " ").replace("'", "")
    s = _non_alnum.sub(" ", s)
    out = []
    for t in s.split():
        t = STREET.get(t, t)
        if t in ADDR_DROP:
            continue
        out.append(t)
    return " ".join(out)


def core_name(n: str) -> str:
    return " ".join(t for t in n.split() if t not in LEGAL)


def process(path: Path, out: Path):
    df = pl.read_csv(path, separator="\t", quote_char=None, infer_schema=False)
    df = df.with_columns(
        pl.col("business_name").fill_null(""),
        pl.col("business_address").fill_null(""),
        pl.col("country").fill_null(""),
    )
    names = [norm_name(x) for x in df["business_name"].to_list()]
    addrs = [norm_addr(x) for x in df["business_address"].to_list()]
    cores = [core_name(n) for n in names]
    nonascii = [0 if x.isascii() else 1 for x in df["business_name"].to_list()]
    df = df.with_columns(
        pl.Series("name", names),
        pl.Series("core", cores),
        pl.Series("addr", addrs),
        pl.Series("name_nonascii", nonascii, dtype=pl.Int8),
    ).with_columns(
        pl.col("core").str.replace_all(" ", "").alias("squash"),
    )
    df.select("entity_id", "country", "name", "core", "squash", "addr",
              "name_nonascii").write_parquet(out)
    print("wrote", out, df.height, flush=True)


if __name__ == "__main__":
    jobs = []
    for split in ("train", "test"):
        for k in ("source1", "source2", "source3"):
            jobs.append((DATA / split / f"{split}_{k}.tsv", WORK / f"{split}_{k}.parquet"))
    from multiprocessing import Pool
    with Pool(3) as p:
        p.starmap(process, jobs)
