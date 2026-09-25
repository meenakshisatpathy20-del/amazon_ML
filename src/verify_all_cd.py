import os
import duckdb

BASE = r"C:\Users\BIT\amazonml"
FEATURE_DIR = os.path.join(BASE, "features")

EXPECTED = {
    "train_s1": 2_206_821,
    "train_s2": 5_034_616,
    "train_s3": 5_285_603,
    "test_s1": 1_732_544,
    "test_s2": 4_887_273,
    "test_s3": 5_082_316,
}

REQUIRED_COLUMNS = {
    "entity_id",
    "business_name",
    "business_address",
    "country",
    "canonical_name",
    "canonical_address",
    "house_number",
    "postal_code",
    "name_tokens",
    "address_tokens",
    "name_token_count",
    "address_token_count",
    "block_prefix_name",
    "block_postal_key",
}

con = duckdb.connect()

try:
    con.execute("PRAGMA threads=8")
except Exception:
    pass


def verify_dataset(name, expected_rows):

    path = os.path.join(
        FEATURE_DIR,
        f"{name}_cd.parquet"
    )

    print()
    print("=" * 80)
    print(name)
    print("=" * 80)

    if not os.path.exists(path):
        print("❌ FILE MISSING")
        return False

    print(f"File: {path}")

    path_sql = path.replace("\\", "/")

    # --------------------------------------------------------
    # ROW COUNT
    # --------------------------------------------------------

    actual_rows = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{path_sql}')
        """
    ).fetchone()[0]

    print(f"Expected rows : {expected_rows:,}")
    print(f"Actual rows   : {actual_rows:,}")

    if actual_rows != expected_rows:
        print("❌ ROW COUNT MISMATCH")
        return False

    print("✓ Row count correct")

    # --------------------------------------------------------
    # SCHEMA
    # --------------------------------------------------------

    schema = con.execute(
        f"""
        DESCRIBE
        SELECT *
        FROM read_parquet('{path_sql}')
        """
    ).fetchall()

    actual_columns = {
        row[0]
        for row in schema
    }

    missing_columns = (
        REQUIRED_COLUMNS
        - actual_columns
    )

    if missing_columns:

        print()
        print("❌ MISSING COLUMNS:")

        for col in sorted(missing_columns):
            print(f"   {col}")

        return False

    print("✓ Required CD columns present")

    # --------------------------------------------------------
    # ENTITY ID QUALITY
    # --------------------------------------------------------

    id_stats = con.execute(
        f"""
        SELECT

            COUNT(*) AS total,

            COUNT(DISTINCT entity_id)
                AS unique_ids,

            COUNT(*) FILTER (
                WHERE entity_id IS NULL
            ) AS null_ids

        FROM read_parquet('{path_sql}')
        """
    ).fetchone()

    total = id_stats[0]
    unique_ids = id_stats[1]
    null_ids = id_stats[2]

    print()
    print("Entity IDs:")
    print(f"  Total       : {total:,}")
    print(f"  Unique      : {unique_ids:,}")
    print(f"  Null        : {null_ids:,}")

    if unique_ids != total or null_ids != 0:
        print("❌ ENTITY ID PROBLEM")
        return False

    print("✓ Entity IDs valid")

    # --------------------------------------------------------
    # CD FIELD QUALITY
    # --------------------------------------------------------

    quality = con.execute(
        f"""
        SELECT

            COUNT(*) FILTER (
                WHERE canonical_name IS NULL
                   OR canonical_name = ''
            ),

            COUNT(*) FILTER (
                WHERE canonical_address IS NULL
                   OR canonical_address = ''
            ),

            COUNT(*) FILTER (
                WHERE name_tokens IS NULL
            ),

            COUNT(*) FILTER (
                WHERE address_tokens IS NULL
            )

        FROM read_parquet('{path_sql}')
        """
    ).fetchone()

    print()
    print("CD fields:")
    print(
        f"  Empty canonical names    : {quality[0]:,}"
    )
    print(
        f"  Empty canonical addresses: {quality[1]:,}"
    )
    print(
        f"  NULL name token arrays   : {quality[2]:,}"
    )
    print(
        f"  NULL address token arrays: {quality[3]:,}"
    )

    # --------------------------------------------------------
    # BLOCKING KEYS
    # --------------------------------------------------------

    block_stats = con.execute(
        f"""
        SELECT

            COUNT(*) FILTER (
                WHERE block_prefix_name <> ''
            ),

            COUNT(*) FILTER (
                WHERE block_postal_key <> ''
            ),

            COUNT(DISTINCT block_prefix_name),

            COUNT(DISTINCT block_postal_key)

        FROM read_parquet('{path_sql}')
        """
    ).fetchone()

    print()
    print("Blocking keys:")
    print(
        f"  Non-empty name keys    : {block_stats[0]:,}"
    )
    print(
        f"  Non-empty postal keys  : {block_stats[1]:,}"
    )
    print(
        f"  Unique name keys       : {block_stats[2]:,}"
    )
    print(
        f"  Unique postal keys     : {block_stats[3]:,}"
    )

    # --------------------------------------------------------
    # UNICODE CHECK
    # --------------------------------------------------------

    unicode_count = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{path_sql}')
        WHERE regexp_matches(
            business_name,
            '[^\\\\x00-\\\\x7F]'
        )
        """
    ).fetchone()[0]

    print()
    print(
        f"Records with Unicode name characters: "
        f"{unicode_count:,}"
    )

    print()
    print("✅ DATASET VERIFIED")

    return True


def main():

    print()
    print("=" * 80)
    print("COMPLETE CD DATASET VERIFICATION")
    print("=" * 80)

    results = {}

    for name, expected in EXPECTED.items():

        results[name] = verify_dataset(
            name,
            expected
        )

    print()
    print("=" * 80)
    print("FINAL VERIFICATION")
    print("=" * 80)

    all_ok = True

    for name, status in results.items():

        if status:
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            all_ok = False

    print()

    if all_ok:

        print(
            "ALL SIX CD DATASETS ARE VERIFIED."
        )

        print()
        print(
            "SAFE TO MOVE TO BLOCKING."
        )

    else:

        print(
            "VERIFICATION FAILED."
        )

        print(
            "DO NOT MOVE TO BLOCKING."
        )


if __name__ == "__main__":
    main()