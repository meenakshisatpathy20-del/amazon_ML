"""
CD IR INSPECTION
================

Inspects the ACTUAL schema produced by preprocess_cd.py.

We verify:

1. Row counts
2. CD columns
3. Missing values
4. Token statistics
5. House numbers
6. Postal codes
7. Blocking keys already generated
8. Unicode records
9. Canonicalization examples
"""

import os
import duckdb


# ============================================================
# PATHS
# ============================================================

BASE = r"C:\Users\BIT\amazonml"
FEATURE_DIR = os.path.join(BASE, "features")


DATASETS = [
    "train_s1",
    "train_s2",
    "train_s3",
    "test_s1",
    "test_s2",
    "test_s3",
]


# ============================================================
# DUCKDB
# ============================================================

con = duckdb.connect()

try:
    con.execute("PRAGMA threads = 8")
except Exception:
    pass


# ============================================================
# PATH
# ============================================================

def parquet_path(dataset):

    return os.path.join(
        FEATURE_DIR,
        f"{dataset}_cd.parquet"
    ).replace("\\", "/")


# ============================================================
# EXISTS
# ============================================================

def file_exists(dataset):

    return os.path.exists(
        os.path.join(
            FEATURE_DIR,
            f"{dataset}_cd.parquet"
        )
    )


# ============================================================
# INSPECT DATASET
# ============================================================

def inspect_dataset(dataset):

    print()
    print("=" * 90)
    print(f"DATASET: {dataset}")
    print("=" * 90)

    if not file_exists(dataset):

        print("STATUS: NOT FOUND")
        return

    path = parquet_path(dataset)

    # --------------------------------------------------------
    # ROW COUNT
    # --------------------------------------------------------

    row_count = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{path}')
        """
    ).fetchone()[0]

    print(f"Rows: {row_count:,}")

    # --------------------------------------------------------
    # SCHEMA
    # --------------------------------------------------------

    print()
    print("COLUMNS:")
    print("-" * 90)

    schema = con.execute(
        f"""
        DESCRIBE
        SELECT *
        FROM read_parquet('{path}')
        """
    ).fetchall()

    column_names = []

    for row in schema:

        column_name = row[0]
        column_type = row[1]

        column_names.append(column_name)

        print(
            f"{column_name:30} {column_type}"
        )

    # --------------------------------------------------------
    # CORE STATISTICS
    # --------------------------------------------------------

    print()
    print("CORE CD STATISTICS:")
    print("-" * 90)

    stats = con.execute(
        f"""
        SELECT

            COUNT(*) AS total_rows,

            COUNT(*) FILTER (
                WHERE canonical_name IS NULL
                   OR canonical_name = ''
            ) AS empty_canonical_name,

            COUNT(*) FILTER (
                WHERE canonical_address IS NULL
                   OR canonical_address = ''
            ) AS empty_canonical_address,

            COUNT(*) FILTER (
                WHERE name_token_count = 0
            ) AS zero_name_tokens,

            COUNT(*) FILTER (
                WHERE address_token_count = 0
            ) AS zero_address_tokens,

            COUNT(*) FILTER (
                WHERE house_number IS NOT NULL
                  AND house_number <> ''
            ) AS with_house_number,

            COUNT(*) FILTER (
                WHERE postal_code IS NOT NULL
                  AND postal_code <> ''
            ) AS with_postal_code,

            COUNT(*) FILTER (
                WHERE block_prefix_name IS NOT NULL
                  AND block_prefix_name <> ''
            ) AS with_name_block_key,

            COUNT(*) FILTER (
                WHERE block_postal_key IS NOT NULL
                  AND block_postal_key <> ''
            ) AS with_postal_block_key

        FROM read_parquet('{path}')
        """
    ).fetchone()

    labels = [
        "Total rows",
        "Empty canonical name",
        "Empty canonical address",
        "Zero name tokens",
        "Zero address tokens",
        "With house number",
        "With postal code",
        "With name block key",
        "With postal block key",
    ]

    for label, value in zip(labels, stats):

        print(
            f"{label:30}: {value:,}"
        )

    # --------------------------------------------------------
    # TOKEN STATISTICS
    # --------------------------------------------------------

    print()
    print("TOKEN STATISTICS:")
    print("-" * 90)

    token_stats = con.execute(
        f"""
        SELECT

            ROUND(
                AVG(name_token_count),
                2
            ) AS avg_name_tokens,

            ROUND(
                AVG(address_token_count),
                2
            ) AS avg_address_tokens,

            MIN(name_token_count),

            MAX(name_token_count),

            MIN(address_token_count),

            MAX(address_token_count)

        FROM read_parquet('{path}')
        """
    ).fetchone()

    print(
        f"Average name tokens    : {token_stats[0]}"
    )

    print(
        f"Average address tokens : {token_stats[1]}"
    )

    print(
        f"Name token range       : "
        f"{token_stats[2]} - {token_stats[3]}"
    )

    print(
        f"Address token range    : "
        f"{token_stats[4]} - {token_stats[5]}"
    )


# ============================================================
# SAMPLE RECORDS
# ============================================================

def show_samples(dataset):

    if not file_exists(dataset):
        return

    path = parquet_path(dataset)

    print()
    print("=" * 90)
    print(f"CD IR SAMPLE RECORDS: {dataset}")
    print("=" * 90)

    rows = con.execute(
        f"""
        SELECT

            entity_id,
            business_name,
            business_address,
            country,

            canonical_name,
            canonical_address,

            name_tokens,
            address_tokens,

            house_number,
            postal_code,

            block_prefix_name,
            block_postal_key

        FROM read_parquet('{path}')

        LIMIT 5
        """
    ).fetchall()

    for row in rows:

        print()
        print("-" * 90)

        print(
            f"Entity ID          : {row[0]}"
        )

        print(
            f"Business name      : {row[1]}"
        )

        print(
            f"Business address   : {row[2]}"
        )

        print(
            f"Country            : {row[3]}"
        )

        print(
            f"Canonical name     : {row[4]}"
        )

        print(
            f"Canonical address  : {row[5]}"
        )

        print(
            f"Name tokens        : {row[6]}"
        )

        print(
            f"Address tokens     : {row[7]}"
        )

        print(
            f"House number       : {row[8]}"
        )

        print(
            f"Postal code        : {row[9]}"
        )

        print(
            f"Name block key     : {row[10]}"
        )

        print(
            f"Postal block key   : {row[11]}"
        )


# ============================================================
# UNICODE EXAMPLES
# ============================================================

def show_unicode_examples(dataset):

    if not file_exists(dataset):
        return

    path = parquet_path(dataset)

    print()
    print("=" * 90)
    print(f"UNICODE RECORDS: {dataset}")
    print("=" * 90)

    rows = con.execute(
        f"""
        SELECT

            entity_id,
            business_name,
            canonical_name,
            name_tokens

        FROM read_parquet('{path}')

        WHERE regexp_matches(
            business_name,
            '[^\\\\x00-\\\\x7F]'
        )

        LIMIT 10
        """
    ).fetchall()

    if not rows:

        print("No Unicode examples found.")
        return

    for row in rows:

        print()
        print(
            f"ID             : {row[0]}"
        )

        print(
            f"Original name  : {row[1]}"
        )

        print(
            f"Canonical name : {row[2]}"
        )

        print(
            f"Name tokens    : {row[3]}"
        )


# ============================================================
# BLOCKING KEY DISTRIBUTION
# ============================================================

def show_blocking_keys(dataset):

    if not file_exists(dataset):
        return

    path = parquet_path(dataset)

    print()
    print("=" * 90)
    print(f"BLOCKING KEY ANALYSIS: {dataset}")
    print("=" * 90)

    result = con.execute(
        f"""
        SELECT

            COUNT(*) AS rows,

            COUNT(DISTINCT block_prefix_name)
                AS unique_name_keys,

            COUNT(DISTINCT block_postal_key)
                AS unique_postal_keys

        FROM read_parquet('{path}')
        """
    ).fetchone()

    print(
        f"Rows                 : {result[0]:,}"
    )

    print(
        f"Unique name block keys: {result[1]:,}"
    )

    print(
        f"Unique postal keys   : {result[2]:,}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 90)
    print("COMPILER-DESIGN IR INSPECTION")
    print("=" * 90)

    print()
    print("Checking actual Parquet schemas.")
    print()

    # --------------------------------------------------------
    # All datasets
    # --------------------------------------------------------

    for dataset in DATASETS:

        inspect_dataset(dataset)

    # --------------------------------------------------------
    # Detailed inspection
    # --------------------------------------------------------

    for dataset in DATASETS:

        if file_exists(dataset):

            show_samples(dataset)
            show_blocking_keys(dataset)

    # --------------------------------------------------------
    # Unicode
    # --------------------------------------------------------

    show_unicode_examples("train_s1")
    show_unicode_examples("train_s2")
    show_unicode_examples("train_s3")

    # --------------------------------------------------------
    # Finish
    # --------------------------------------------------------

    print()
    print("=" * 90)
    print("IR INSPECTION COMPLETE")
    print("=" * 90)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()