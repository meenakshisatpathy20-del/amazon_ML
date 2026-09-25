import os
import duckdb


# ============================================================
# PATHS
# ============================================================

BASE = r"C:\Users\BIT\amazonml"

TRAIN_DIR = os.path.join(
    BASE,
    "data",
    "raw",
    "train"
)

TEST_DIR = os.path.join(
    BASE,
    "data",
    "raw",
    "test"
)

FEATURE_DIR = os.path.join(
    BASE,
    "features"
)

os.makedirs(
    FEATURE_DIR,
    exist_ok=True
)


# ============================================================
# DATASETS
# ============================================================

DATASETS = {
    "train_s1": (
        os.path.join(TRAIN_DIR, "train_source1.tsv"),
        2_206_821
    ),

    "train_s2": (
        os.path.join(TRAIN_DIR, "train_source2.tsv"),
        5_034_616
    ),

    "train_s3": (
        os.path.join(TRAIN_DIR, "train_source3.tsv"),
        5_285_603
    ),

    "test_s1": (
        os.path.join(TEST_DIR, "test_source1.tsv"),
        1_732_544
    ),

    "test_s2": (
        os.path.join(TEST_DIR, "test_source2.tsv"),
        4_887_273
    ),

    "test_s3": (
        os.path.join(TEST_DIR, "test_source3.tsv"),
        5_082_316
    ),
}


# ============================================================
# DUCKDB
# ============================================================

con = duckdb.connect()

try:
    con.execute("PRAGMA threads=8")
except Exception:
    pass


# ============================================================
# SQL PATH
# ============================================================

def sql_path(path):

    return (
        path
        .replace("\\", "/")
        .replace("'", "''")
    )


# ============================================================
# PROCESS ONE DATASET
# ============================================================

def process_dataset(
    dataset_name,
    input_file,
    expected_rows
):

    output_file = os.path.join(
        FEATURE_DIR,
        f"{dataset_name}_cd.parquet"
    )

    print()
    print("=" * 80)
    print(f"CD PREPROCESSING: {dataset_name}")
    print("=" * 80)

    print(f"Input : {input_file}")
    print(f"Output: {output_file}")
    print(f"Expected rows: {expected_rows:,}")
    print()

    if not os.path.exists(input_file):

        print("❌ INPUT FILE DOES NOT EXIST")
        return False

    input_sql = sql_path(input_file)
    output_sql = sql_path(output_file)

    # --------------------------------------------------------
    # Remove an old incomplete output, if present
    # --------------------------------------------------------

    if os.path.exists(output_file):

        print("Removing previous output...")

        os.remove(output_file)

    # --------------------------------------------------------
    # READ → NORMALIZE → SYMBOL TABLE → LEXER/IR
    # --------------------------------------------------------

    query = f"""

    COPY
    (

        WITH raw AS
        (
            SELECT

                entity_id,
                business_name,
                business_address,
                country

            FROM read_csv(
                '{input_sql}',
                delim='\\t',
                header=true,
                all_varchar=true,
                nullstr=''
            )
        ),

        --------------------------------------------------------
        -- BASIC NORMALIZATION
        --------------------------------------------------------

        cleaned AS
        (
            SELECT

                entity_id,
                business_name,
                business_address,
                country,

                lower(
                    trim(
                        regexp_replace(
                            business_name,
                            '\\\\s+',
                            ' ',
                            'g'
                        )
                    )
                ) AS name_lower,

                lower(
                    trim(
                        regexp_replace(
                            coalesce(
                                business_address,
                                ''
                            ),
                            '\\\\s+',
                            ' ',
                            'g'
                        )
                    )
                ) AS address_lower

            FROM raw
        ),

        --------------------------------------------------------
        -- ACCENT NORMALIZATION
        --------------------------------------------------------

        normalized AS
        (
            SELECT

                *,

                strip_accents(
                    name_lower
                ) AS name_normalized,

                strip_accents(
                    address_lower
                ) AS address_normalized

            FROM cleaned
        ),

        --------------------------------------------------------
        -- SYMBOL TABLE:
        -- LEGAL SUFFIXES
        --------------------------------------------------------

        legal_canonical AS
        (
            SELECT

                *,

                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                regexp_replace(
                                    regexp_replace(
                                        regexp_replace(
                                            regexp_replace(

                                                name_normalized,

                                                '\\binc\\.?\\b|\\bincorporated\\b',
                                                ' incorporated ',
                                                'gi'
                                            ),

                                            '\\bltd\\.?\\b|\\blimited\\b',
                                            ' limited ',
                                            'gi'
                                        ),

                                        '\\bpvt\\.?\\b|\\bprivate\\b',
                                        ' private ',
                                        'gi'
                                    ),

                                    '\\bllc\\b|\\bl\\.l\\.c\\b',
                                    ' limited_liability_company ',
                                    'gi'
                                ),

                                '\\bplc\\b',
                                ' public_limited_company ',
                                'gi'
                            ),

                            '\\bllp\\b',
                            ' limited_liability_partnership ',
                            'gi'
                        ),

                        '\\bcorp\\.?\\b|\\bcorporation\\b',
                        ' corporation ',
                        'gi'
                    ),

                    '\\bco\\.?\\b|\\bcompany\\b',
                    ' company ',
                    'gi'

                ) AS canonical_name

            FROM normalized
        ),

        --------------------------------------------------------
        -- SYMBOL TABLE:
        -- ADDRESS ABBREVIATIONS
        --------------------------------------------------------

        address_canonical AS
        (
            SELECT

                *,

                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                regexp_replace(
                                    regexp_replace(
                                        regexp_replace(
                                            regexp_replace(

                                                address_normalized,

                                                '\\brd\\.?\\b',
                                                ' road ',
                                                'gi'
                                            ),

                                            '\\bst\\.?\\b',
                                            ' street ',
                                            'gi'
                                        ),

                                        '\\bave\\.?\\b',
                                        ' avenue ',
                                        'gi'
                                    ),

                                    '\\bblvd\\.?\\b',
                                    ' boulevard ',
                                    'gi'
                                ),

                                '\\bdr\\.?\\b',
                                ' drive ',
                                'gi'
                            ),

                            '\\bln\\.?\\b',
                            ' lane ',
                            'gi'
                        ),

                        '\\bct\\.?\\b',
                        ' court ',
                        'gi'
                    ),

                    '\\bhwy\\.?\\b',
                    ' highway ',
                    'gi'

                ) AS canonical_address

            FROM legal_canonical
        ),

        --------------------------------------------------------
        -- CLEAN CANONICAL STRINGS
        --------------------------------------------------------

        canonical AS
        (
            SELECT

                *,

                trim(
                    regexp_replace(
                        canonical_name,
                        '\\\\s+',
                        ' ',
                        'g'
                    )
                ) AS final_name,

                trim(
                    regexp_replace(
                        canonical_address,
                        '\\\\s+',
                        ' ',
                        'g'
                    )
                ) AS final_address

            FROM address_canonical
        ),

        --------------------------------------------------------
        -- CD LEXER
        --
        -- Unicode letters + Unicode numbers
        --------------------------------------------------------

        lexical AS
        (
            SELECT

                *,

                regexp_extract_all(
                    final_name,
                    '\\\\p{{L}}+|\\\\p{{N}}+'
                ) AS name_tokens,

                regexp_extract_all(
                    final_address,
                    '\\\\p{{L}}+|\\\\p{{N}}+'
                ) AS address_tokens

            FROM canonical
        ),

        --------------------------------------------------------
        -- TOKEN INFORMATION
        --------------------------------------------------------

        token_info AS
        (
            SELECT

                *,

                len(name_tokens)
                    AS name_token_count,

                len(address_tokens)
                    AS address_token_count

            FROM lexical
        ),

        --------------------------------------------------------
        -- HOUSE NUMBER
        --------------------------------------------------------

        house_info AS
        (
            SELECT

                *,

                coalesce(
                    regexp_extract(
                        final_address,
                        '^\\\\s*([0-9]+(?:-[0-9]+)?)',
                        1
                    ),
                    ''
                ) AS house_number

            FROM token_info
        ),

        --------------------------------------------------------
        -- POSTAL CODE
        --------------------------------------------------------

        postal_info AS
        (
            SELECT

                *,

                coalesce(
                    regexp_extract(
                        final_address,
                        '\\\\b([0-9]{{5}}(?:-[0-9]{{4}})?)\\\\b',
                        1
                    ),
                    ''
                ) AS postal_us,

                coalesce(
                    regexp_extract(
                        final_address,
                        '\\\\b([0-9]{{6}})\\\\b',
                        1
                    ),
                    ''
                ) AS postal_india

            FROM house_info
        ),

        --------------------------------------------------------
        -- BLOCKING KEYS
        --------------------------------------------------------

        blocking_keys AS
        (
            SELECT

                *,

                ------------------------------------------------
                -- First 3 normalized name tokens/characters
                ------------------------------------------------

                CASE

                    WHEN length(final_name) >= 3

                    THEN left(
                        regexp_replace(
                            final_name,
                            '[^\\\\p{{L}}\\\\p{{N}}]',
                            '',
                            'g'
                        ),
                        3
                    )

                    ELSE final_name

                END AS block_prefix_name,

                ------------------------------------------------
                -- Postal blocking key
                ------------------------------------------------

                CASE

                    WHEN postal_us <> ''

                    THEN postal_us

                    WHEN postal_india <> ''

                    THEN postal_india

                    ELSE ''

                END AS block_postal_key

            FROM postal_info
        ),

        --------------------------------------------------------
        -- FINAL CD INTERMEDIATE REPRESENTATION
        --------------------------------------------------------

        final_ir AS
        (
            SELECT

                entity_id,

                business_name,
                business_address,
                country,

                canonical_name
                    AS canonical_name,

                final_address
                    AS canonical_address,

                house_number,

                CASE

                    WHEN postal_us <> ''

                    THEN postal_us

                    ELSE postal_india

                END AS postal_code,

                name_tokens,
                address_tokens,

                name_token_count,
                address_token_count,

                block_prefix_name,
                block_postal_key

            FROM blocking_keys
        )

        SELECT *

        FROM final_ir

    )

    TO '{output_sql}'

    (
        FORMAT PARQUET,
        COMPRESSION ZSTD
    );

    """

    try:

        con.execute(query)

        # ----------------------------------------------------
        # IMMEDIATE VERIFICATION
        # ----------------------------------------------------

        actual_rows = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet(
                '{output_sql}'
            )
            """
        ).fetchone()[0]

        print()
        print(
            f"Actual rows: {actual_rows:,}"
        )

        if actual_rows != expected_rows:

            print()
            print("❌ ROW COUNT MISMATCH")

            print(
                f"Expected: {expected_rows:,}"
            )

            print(
                f"Actual  : {actual_rows:,}"
            )

            return False

        print()
        print("✓ Row count verified")
        print("✓ Parquet created")
        print("✓ Dataset complete")

        return True

    except Exception as e:

        print()
        print("❌ PREPROCESSING ERROR")
        print("-" * 80)
        print(str(e))
        print("-" * 80)

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("COMPLETE CD PREPROCESSING")
    print("=" * 80)

    print()
    print(
        "Processing ALL SIX entity datasets."
    )

    results = {}

    # --------------------------------------------------------
    # Process every dataset
    # --------------------------------------------------------

    for name, (file_path, expected_rows) in DATASETS.items():

        results[name] = process_dataset(
            name,
            file_path,
            expected_rows
        )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("FINAL CD PREPROCESSING SUMMARY")
    print("=" * 80)

    for name, status in results.items():

        if status:

            print(
                f"✅ {name}"
            )

        else:

            print(
                f"❌ {name}"
            )

    print()

    if all(results.values()):

        print(
            "ALL SIX DATASETS PROCESSED AND VERIFIED."
        )

    else:

        print(
            "PROCESSING FAILED FOR ONE OR MORE DATASETS."
        )

        print(
            "DO NOT MOVE TO BLOCKING."
        )


if __name__ == "__main__":
    main()