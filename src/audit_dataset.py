import duckdb
import os

# ============================================================
# AMAZON BUSINESS ENTITY RESOLUTION
# COMPLETE DATASET AUDIT
# ============================================================

con = duckdb.connect()

TRAIN_DIR = "data/raw/train"
TEST_DIR = "data/raw/test"

files = [
    ("TRAIN_SOURCE1", f"{TRAIN_DIR}/train_source1.tsv"),
    ("TRAIN_SOURCE2", f"{TRAIN_DIR}/train_source2.tsv"),
    ("TRAIN_SOURCE3", f"{TRAIN_DIR}/train_source3.tsv"),
    ("TRAIN_GROUND_TRUTH", f"{TRAIN_DIR}/train_ground_truth.tsv"),
    ("TEST_SOURCE1", f"{TEST_DIR}/test_source1.tsv"),
    ("TEST_SOURCE2", f"{TEST_DIR}/test_source2.tsv"),
    ("TEST_SOURCE3", f"{TEST_DIR}/test_source3.tsv"),
]


def read_csv_sql(file):
    return f"""
        read_csv(
            '{file}',
            delim = '\t',
            header = true,
            all_varchar = true
        )
    """


print("=" * 80)
print("AMAZON BUSINESS ENTITY RESOLUTION - DATASET AUDIT")
print("=" * 80)


for name, file in files:

    print("\n")
    print("=" * 80)
    print(name)
    print("=" * 80)

    # --------------------------------------------------------
    # Check file exists
    # --------------------------------------------------------

    if not os.path.exists(file):
        print("ERROR: File not found:", file)
        continue

    file_size_mb = os.path.getsize(file) / (1024 * 1024)

    print(f"File: {file}")
    print(f"Size: {file_size_mb:.2f} MB")

    # --------------------------------------------------------
    # Column information
    # --------------------------------------------------------

    columns_result = con.execute(
        f"DESCRIBE SELECT * FROM {read_csv_sql(file)}"
    ).fetchall()

    print("\nColumns:")

    columns = []

    for row in columns_result:
        column_name = row[0]
        column_type = row[1]

        columns.append(column_name)

        print(f"  {column_name} -> {column_type}")

    # --------------------------------------------------------
    # Row count
    # --------------------------------------------------------

    count_result = con.execute(
        f"SELECT COUNT(*) FROM {read_csv_sql(file)}"
    ).fetchone()

    row_count = count_result[0]

    print(f"\nTotal rows: {row_count:,}")

    # --------------------------------------------------------
    # ID statistics
    # --------------------------------------------------------

    if "entity_id" in columns:

        id_stats = con.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT entity_id) AS unique_ids,
                COUNT(*) - COUNT(entity_id) AS null_ids
            FROM {read_csv_sql(file)}
            """
        ).fetchone()

        print("\nEntity ID statistics:")
        print(f"  Total IDs:       {id_stats[0]:,}")
        print(f"  Unique IDs:      {id_stats[1]:,}")
        print(f"  Null IDs:        {id_stats[2]:,}")
        print(f"  Duplicate IDs:   {id_stats[0] - id_stats[1]:,}")

    # --------------------------------------------------------
    # Source files
    # --------------------------------------------------------

    if "business_name" in columns:

        name_stats = con.execute(
            f"""
            SELECT
                COUNT(*) - COUNT(NULLIF(TRIM(business_name), '')) AS missing_names,
                MIN(LENGTH(business_name)) AS min_name_length,
                MAX(LENGTH(business_name)) AS max_name_length,
                AVG(LENGTH(business_name)) AS avg_name_length
            FROM {read_csv_sql(file)}
            """
        ).fetchone()

        print("\nBusiness name statistics:")
        print(f"  Missing/empty:   {name_stats[0]:,}")
        print(f"  Minimum length:  {name_stats[1]}")
        print(f"  Maximum length:  {name_stats[2]}")
        print(f"  Average length:  {name_stats[3]:.2f}")

    # --------------------------------------------------------
    # Address statistics
    # --------------------------------------------------------

    if "business_address" in columns:

        address_stats = con.execute(
            f"""
            SELECT
                COUNT(*) - COUNT(NULLIF(TRIM(business_address), '')) AS missing_addresses,
                MIN(LENGTH(business_address)) AS min_address_length,
                MAX(LENGTH(business_address)) AS max_address_length,
                AVG(LENGTH(business_address)) AS avg_address_length
            FROM {read_csv_sql(file)}
            """
        ).fetchone()

        print("\nBusiness address statistics:")
        print(f"  Missing/empty:   {address_stats[0]:,}")
        print(f"  Minimum length:  {address_stats[1]}")
        print(f"  Maximum length:  {address_stats[2]}")
        print(f"  Average length:  {address_stats[3]:.2f}")

    # --------------------------------------------------------
    # Country statistics
    # --------------------------------------------------------

    if "country" in columns:

        print("\nCountries:")

        countries = con.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM(country), ''), '<MISSING>') AS country,
                COUNT(*) AS count
            FROM {read_csv_sql(file)}
            GROUP BY country
            ORDER BY count DESC
            """
        ).fetchall()

        for country, count in countries:
            print(f"  {country}: {count:,}")

    # --------------------------------------------------------
    # Ground truth statistics
    # --------------------------------------------------------

    if name == "TRAIN_GROUND_TRUTH":

        print("\nGround truth statistics:")

        gt_stats = con.execute(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT source1_entity_id) AS unique_source1,
                COUNT(*) - COUNT(source1_entity_id) AS missing_source1
            FROM {read_csv_sql(file)}
            """
        ).fetchone()

        print(f"  Total rows:           {gt_stats[0]:,}")
        print(f"  Unique S1 entities:   {gt_stats[1]:,}")
        print(f"  Missing S1 IDs:       {gt_stats[2]:,}")

        # Number of matches per S1
        match_stats = con.execute(
            f"""
            SELECT
                MIN(
                    CASE
                        WHEN matched_entity_ids IS NULL
                             OR TRIM(matched_entity_ids) = ''
                        THEN 0
                        ELSE LENGTH(matched_entity_ids)
                             - LENGTH(REPLACE(matched_entity_ids, ',', ''))
                             + 1
                    END
                ) AS min_matches,
                MAX(
                    CASE
                        WHEN matched_entity_ids IS NULL
                             OR TRIM(matched_entity_ids) = ''
                        THEN 0
                        ELSE LENGTH(matched_entity_ids)
                             - LENGTH(REPLACE(matched_entity_ids, ',', ''))
                             + 1
                    END
                ) AS max_matches,
                AVG(
                    CASE
                        WHEN matched_entity_ids IS NULL
                             OR TRIM(matched_entity_ids) = ''
                        THEN 0
                        ELSE LENGTH(matched_entity_ids)
                             - LENGTH(REPLACE(matched_entity_ids, ',', ''))
                             + 1
                    END
                ) AS avg_matches
            FROM {read_csv_sql(file)}
            """
        ).fetchone()

        print("\nMatches per Source-1 entity:")
        print(f"  Minimum matches: {match_stats[0]}")
        print(f"  Maximum matches: {match_stats[1]}")
        print(f"  Average matches: {match_stats[2]:.2f}")


print("\n")
print("=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)

con.close()