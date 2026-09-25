import os
import duckdb

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


def sql_path(path: str) -> str:
    return path.replace("\\", "/").replace("'", "''")


def main():
    print("\n" + "=" * 90)
    print("CD TOKEN REPAIR (OPTIMIZED UNICODE EXTRACTION)")
    print("=" * 90)

    con = duckdb.connect()
    con.execute("PRAGMA threads=8;")
    con.execute("PRAGMA preserve_insertion_order=false;")

    for i, dataset in enumerate(DATASETS, 1):
        input_file = os.path.join(FEATURE_DIR, f"{dataset}_cd.parquet")
        temp_file = os.path.join(FEATURE_DIR, f"{dataset}_cd_fixed.parquet")

        if not os.path.exists(input_file):
            print(f"[{i}/6] Skipping {dataset}: {input_file} not found.")
            continue

        inp = sql_path(input_file)
        tmp = sql_path(temp_file)

        print(f"\n[{i}/6] Repairing {dataset}...")

        try:
            # 1. Rebuild token arrays using a single-pass extraction CTE
            # [\p{L}\p{N}]+ captures full Unicode alphanumeric ranges in RE2
            con.execute(f"""
                COPY (
                    WITH extracted AS (
                        SELECT
                            entity_id,
                            business_name,
                            business_address,
                            country,
                            canonical_name,
                            canonical_address,
                            house_number,
                            postal_code,
                            regexp_extract_all(coalesce(canonical_name, ''), '[\\p{{L}}\\p{{N}}]+') AS name_tokens,
                            regexp_extract_all(coalesce(canonical_address, ''), '[\\p{{L}}\\p{{N}}]+') AS address_tokens,
                            block_prefix_name,
                            block_postal_key
                        FROM read_parquet('{inp}')
                    )
                    SELECT
                        entity_id,
                        business_name,
                        business_address,
                        country,
                        canonical_name,
                        canonical_address,
                        house_number,
                        postal_code,
                        name_tokens,
                        address_tokens,
                        len(name_tokens) AS name_token_count,
                        len(address_tokens) AS address_token_count,
                        block_prefix_name,
                        block_postal_key
                    FROM extracted
                )
                TO '{tmp}'
                (FORMAT PARQUET, COMPRESSION ZSTD);
            """)

            # 2. Single-pass verification query (reads target Parquet exactly once)
            old_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{inp}')").fetchone()[0]

            stats = con.execute(f"""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(CASE WHEN len(name_tokens) > 0 THEN 1 END) AS non_empty_names,
                    COUNT(CASE WHEN len(address_tokens) > 0 THEN 1 END) AS non_empty_addresses
                FROM read_parquet('{tmp}')
            """).fetchone()

            new_count, non_empty_names, non_empty_addresses = stats

            print(f"  Rows Processed        : {new_count:,} / Expected: {old_count:,}")
            print(f"  Non-empty name tokens : {non_empty_names:,}")
            print(f"  Non-empty addr tokens : {non_empty_addresses:,}")

            if old_count != new_count:
                raise RuntimeError(
                    f"Row count mismatch for {dataset}: expected {old_count}, got {new_count}"
                )

            # 3. Replace original file atomically
            os.replace(temp_file, input_file)
            print(f"  Status                : Successfully replaced original Parquet.")

        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            print(f"  Error processing {dataset}: {e}")
            raise e

    con.close()
    print("\n" + "=" * 90)
    print("ALL SIX CD PARQUETS TOKEN-REPAIRED SUCCESSFULLY")
    print("=" * 90)


if __name__ == "__main__":
    main()