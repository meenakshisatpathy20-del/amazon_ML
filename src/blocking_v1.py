import os
import shutil
import duckdb


# ============================================================
# CONFIGURATION
# ============================================================

BASE = r"C:\Users\BIT\amazonml"

FEATURE_DIR = os.path.join(BASE, "features")
REPORT_DIR = os.path.join(BASE, "reports")
TEMP_DIR = os.path.join(FEATURE_DIR, "duckdb_blocking_tmp")

os.makedirs(FEATURE_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


S1_FILE = os.path.join(
    FEATURE_DIR,
    "train_s1_cd.parquet"
)

S2_FILE = os.path.join(
    FEATURE_DIR,
    "train_s2_cd.parquet"
)

S3_FILE = os.path.join(
    FEATURE_DIR,
    "train_s3_cd.parquet"
)

GT_FILE = os.path.join(
    BASE,
    "data",
    "raw",
    "train",
    "train_ground_truth.tsv"
)

OUTPUT_FILE = os.path.join(
    FEATURE_DIR,
    "train_candidate_pairs_labeled.parquet"
)

DB_FILE = os.path.join(
    FEATURE_DIR,
    "blocking_work.duckdb"
)


# ============================================================
# SQL PATH HELPER
# ============================================================

def sql_path(path):

    return (
        path
        .replace("\\", "/")
        .replace("'", "''")
    )


S1 = sql_path(S1_FILE)
S2 = sql_path(S2_FILE)
S3 = sql_path(S3_FILE)
GT = sql_path(GT_FILE)
OUT = sql_path(OUTPUT_FILE)
TMP = sql_path(TEMP_DIR)
DB = sql_path(DB_FILE)


# ============================================================
# DUCKDB CONNECTION
# ============================================================

con = duckdb.connect(DB)

# Memory-safe configuration.
#
# Lower thread count reduces simultaneous memory pressure.
con.execute("SET threads=2")

# Allows DuckDB to reorder results and reduce memory usage.
con.execute("SET preserve_insertion_order=false")

# Keep working memory below the system limit so that
# DuckDB can use disk spilling safely.
con.execute("SET memory_limit='8GB'")

# Explicit temporary directory for spilling.
con.execute(
    f"SET temp_directory='{TMP}'"
)

# Allow substantial temporary spill space.
try:
    con.execute(
        "SET max_temp_directory_size='50GB'"
    )
except Exception:
    pass


# ============================================================
# UTILITY
# ============================================================

def count_table(table):

    return con.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]


def print_stage(title):

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


# ============================================================
# MAIN
# ============================================================

def main():

    print_stage(
        "ENTITY RESOLUTION BLOCKING V2 - MEMORY SAFE"
    )

    print(
        "DuckDB threads       : 2"
    )

    print(
        "DuckDB memory limit  : 8GB"
    )

    print(
        "Temp spill directory :"
    )

    print(
        f"  {TEMP_DIR}"
    )

    # ========================================================
    # CLEAN OLD WORK TABLES
    # ========================================================

    for table in [
        "s1",
        "s2",
        "s3",
        "stop_tokens",
        "s1_tokens",
        "s2_tokens",
        "s3_tokens",
        "s2_token_freq",
        "s3_token_freq",
        "candidate_pairs",
        "true_pairs",
    ]:

        try:
            con.execute(
                f"DROP TABLE IF EXISTS {table}"
            )
        except Exception:
            pass

    # ========================================================
    # 1. LOAD CD DATA
    # ========================================================

    print_stage(
        "[1/7] Loading CD Parquets"
    )

    con.execute(
        f"""
        CREATE TABLE s1 AS

        SELECT
            entity_id,
            country,
            canonical_name,
            canonical_address,
            house_number,
            postal_code,
            name_tokens,
            address_tokens,
            block_prefix_name,
            block_postal_key

        FROM read_parquet('{S1}')
        """
    )

    print(
        f"S1 rows: {count_table('s1'):,}"
    )


    con.execute(
        f"""
        CREATE TABLE s2 AS

        SELECT
            entity_id,
            country,
            canonical_name,
            canonical_address,
            house_number,
            postal_code,
            name_tokens,
            address_tokens,
            block_prefix_name,
            block_postal_key

        FROM read_parquet('{S2}')
        """
    )

    print(
        f"S2 rows: {count_table('s2'):,}"
    )


    con.execute(
        f"""
        CREATE TABLE s3 AS

        SELECT
            entity_id,
            country,
            canonical_name,
            canonical_address,
            house_number,
            postal_code,
            name_tokens,
            address_tokens,
            block_prefix_name,
            block_postal_key

        FROM read_parquet('{S3}')
        """
    )

    print(
        f"S3 rows: {count_table('s3'):,}"
    )


    # ========================================================
    # 2. STOP TOKENS
    # ========================================================

    print_stage(
        "[2/7] Building selective token indexes"
    )

    con.execute(
        """
        CREATE TABLE stop_tokens AS

        SELECT *

        FROM (
            VALUES

            ('inc'),
            ('incorporated'),
            ('ltd'),
            ('limited'),
            ('llc'),
            ('llp'),
            ('plc'),
            ('corp'),
            ('corporation'),
            ('company'),
            ('co'),
            ('private'),
            ('pvt'),
            ('public'),
            ('the'),
            ('and'),
            ('of'),
            ('for'),
            ('group'),
            ('services'),
            ('service'),
            ('solutions'),
            ('international'),
            ('india'),
            ('ind'),
            ('usa'),
            ('us')

        ) AS x(token)
        """
    )


    # ========================================================
    # S2 TOKEN FREQUENCY
    # ========================================================

    con.execute(
        """
        CREATE TABLE s2_token_freq AS

        SELECT

            token,

            COUNT(DISTINCT entity_id) AS df

        FROM
        (
            SELECT

                entity_id,

                unnest(name_tokens) AS token

            FROM s2
        ) x

        WHERE

            token IS NOT NULL

            AND length(token) >= 4

            AND token NOT IN
            (
                SELECT token
                FROM stop_tokens
            )

        GROUP BY token
        """
    )


    # ========================================================
    # S3 TOKEN FREQUENCY
    # ========================================================

    con.execute(
        """
        CREATE TABLE s3_token_freq AS

        SELECT

            token,

            COUNT(DISTINCT entity_id) AS df

        FROM
        (
            SELECT

                entity_id,

                unnest(name_tokens) AS token

            FROM s3
        ) x

        WHERE

            token IS NOT NULL

            AND length(token) >= 4

            AND token NOT IN
            (
                SELECT token
                FROM stop_tokens
            )

        GROUP BY token
        """
    )


    print(
        "S2 informative tokens:",
        con.execute(
            "SELECT COUNT(*) FROM s2_token_freq"
        ).fetchone()[0]
    )

    print(
        "S3 informative tokens:",
        con.execute(
            "SELECT COUNT(*) FROM s3_token_freq"
        ).fetchone()[0]
    )


    # ========================================================
    # S1 TOKENS
    # ========================================================

    con.execute(
        """
        CREATE TABLE s1_tokens AS

        SELECT DISTINCT

            s.entity_id AS source1_entity_id,

            s.country,

            u.token

        FROM s1 s

        CROSS JOIN LATERAL
            unnest(s.name_tokens) AS u(token)

        WHERE

            u.token IS NOT NULL

            AND length(u.token) >= 4

            AND u.token NOT IN
            (
                SELECT token
                FROM stop_tokens
            )
        """
    )


    # ========================================================
    # S2 TOKENS
    # ========================================================

    con.execute(
        """
        CREATE TABLE s2_tokens AS

        SELECT DISTINCT

            s.entity_id AS candidate_entity_id,

            s.country,

            u.token

        FROM s2 s

        CROSS JOIN LATERAL
            unnest(s.name_tokens) AS u(token)

        WHERE

            u.token IS NOT NULL

            AND length(u.token) >= 4

            AND u.token NOT IN
            (
                SELECT token
                FROM stop_tokens
            )
        """
    )


    # ========================================================
    # S3 TOKENS
    # ========================================================

    con.execute(
        """
        CREATE TABLE s3_tokens AS

        SELECT DISTINCT

            s.entity_id AS candidate_entity_id,

            s.country,

            u.token

        FROM s3 s

        CROSS JOIN LATERAL
            unnest(s.name_tokens) AS u(token)

        WHERE

            u.token IS NOT NULL

            AND length(u.token) >= 4

            AND u.token NOT IN
            (
                SELECT token
                FROM stop_tokens
            )
        """
    )


    # ========================================================
    # CANDIDATE TABLE
    # ========================================================

    con.execute(
        """
        CREATE TABLE candidate_pairs
        (
            source1_entity_id VARCHAR,
            candidate_entity_id VARCHAR,
            candidate_source VARCHAR,

            rule_exact_name INTEGER,
            rule_prefix INTEGER,
            rule_postal_token INTEGER,
            rule_house_token INTEGER,
            rule_rare_token INTEGER
        )
        """
    )


    # ========================================================
    # PASS 1
    # EXACT CANONICAL NAME
    # ========================================================

    print_stage(
        "[3/7] Running multi-pass candidate generation"
    )

    print(
        "PASS 1: Exact canonical name"
    )

    con.execute(
        """
        INSERT INTO candidate_pairs

        SELECT

            s1.entity_id,

            s2.entity_id,

            'S2',

            1, 0, 0, 0, 0

        FROM s1

        INNER JOIN s2

            ON s1.canonical_name =
               s2.canonical_name

        WHERE

            s1.canonical_name <> ''

            AND s2.canonical_name <> ''

        UNION ALL

        SELECT

            s1.entity_id,

            s3.entity_id,

            'S3',

            1, 0, 0, 0, 0

        FROM s1

        INNER JOIN s3

            ON s1.canonical_name =
               s3.canonical_name

        WHERE

            s1.canonical_name <> ''

            AND s3.canonical_name <> ''
        """
    )

    print(
        "Pairs after exact name:",
        count_table("candidate_pairs")
    )


    # ========================================================
    # PASS 2
    # PREFIX
    # ========================================================

    print(
        "PASS 2: Name prefix"
    )

    con.execute(
        """
        INSERT INTO candidate_pairs

        SELECT

            s1.entity_id,

            s2.entity_id,

            'S2',

            0, 1, 0, 0, 0

        FROM s1

        INNER JOIN s2

            ON s1.block_prefix_name =
               s2.block_prefix_name

        WHERE

            s1.block_prefix_name <> ''

            AND length(s1.block_prefix_name) >= 3

            AND s2.block_prefix_name <> ''

        UNION ALL

        SELECT

            s1.entity_id,

            s3.entity_id,

            'S3',

            0, 1, 0, 0, 0

        FROM s1

        INNER JOIN s3

            ON s1.block_prefix_name =
               s3.block_prefix_name

        WHERE

            s1.block_prefix_name <> ''

            AND length(s1.block_prefix_name) >= 3

            AND s3.block_prefix_name <> ''
        """
    )

    print(
        "Pairs after prefix:",
        count_table("candidate_pairs")
    )


    # ========================================================
    # PASS 3
    # POSTAL + INFORMATIVE TOKEN
    #
    # Postal fields are sparse in this dataset, so this pass
    # is safe and contributes only where postal exists.
    # ========================================================

    print(
        "PASS 3: Postal + informative token"
    )

    con.execute(
        """
        INSERT INTO candidate_pairs

        SELECT DISTINCT

            st.source1_entity_id,

            st2.candidate_entity_id,

            'S2',

            0, 0, 1, 0, 0

        FROM s1_tokens st

        INNER JOIN s2_token_freq f

            ON f.token = st.token

            AND f.df <= 1500

        INNER JOIN s2_tokens st2

            ON st2.token = st.token

            AND st2.country = st.country

        INNER JOIN s2 s2x

            ON s2x.entity_id =
               st2.candidate_entity_id

            AND s2x.postal_code =

                (
                    SELECT postal_code
                    FROM s1
                    WHERE entity_id =
                          st.source1_entity_id
                )

        WHERE

            s2x.postal_code <> ''

        UNION ALL

        SELECT DISTINCT

            st.source1_entity_id,

            st3.candidate_entity_id,

            'S3',

            0, 0, 1, 0, 0

        FROM s1_tokens st

        INNER JOIN s3_token_freq f

            ON f.token = st.token

            AND f.df <= 1500

        INNER JOIN s3_tokens st3

            ON st3.token = st.token

            AND st3.country = st.country

        INNER JOIN s3 s3x

            ON s3x.entity_id =
               st3.candidate_entity_id

            AND s3x.postal_code =

                (
                    SELECT postal_code
                    FROM s1
                    WHERE entity_id =
                          st.source1_entity_id
                )

        WHERE

            s3x.postal_code <> ''
        """
    )

    print(
        "Pairs after postal:",
        count_table("candidate_pairs")
    )


    # ========================================================
    # PASS 4
    # HOUSE NUMBER + INFORMATIVE TOKEN
    # ========================================================

    print(
        "PASS 4: House number + informative token"
    )

    con.execute(
        """
        INSERT INTO candidate_pairs

        SELECT DISTINCT

            st.source1_entity_id,

            st2.candidate_entity_id,

            'S2',

            0, 0, 0, 1, 0

        FROM s1_tokens st

        INNER JOIN s2_token_freq f

            ON f.token = st.token

            AND f.df <= 1500

        INNER JOIN s2_tokens st2

            ON st2.token = st.token

            AND st2.country = st.country

        INNER JOIN s2 s2x

            ON s2x.entity_id =
               st2.candidate_entity_id

            AND s2x.house_number =

                (
                    SELECT house_number
                    FROM s1
                    WHERE entity_id =
                          st.source1_entity_id
                )

        WHERE

            s2x.house_number <> ''

        UNION ALL

        SELECT DISTINCT

            st.source1_entity_id,

            st3.candidate_entity_id,

            'S3',

            0, 0, 0, 1, 0

        FROM s1_tokens st

        INNER JOIN s3_token_freq f

            ON f.token = st.token

            AND f.df <= 1500

        INNER JOIN s3_tokens st3

            ON st3.token = st.token

            AND st3.country = st.country

        INNER JOIN s3 s3x

            ON s3x.entity_id =
               st3.candidate_entity_id

            AND s3x.house_number =

                (
                    SELECT house_number
                    FROM s1
                    WHERE entity_id =
                          st.source1_entity_id
                )

        WHERE

            s3x.house_number <> ''
        """
    )

    print(
        "Pairs after house number:",
        count_table("candidate_pairs")
    )


    # ========================================================
    # PASS 5
    # RARE INFORMATIVE TOKEN
    # ========================================================

    print(
        "PASS 5: Rare informative token"
    )

    con.execute(
        """
        INSERT INTO candidate_pairs

        SELECT DISTINCT

            st.source1_entity_id,

            st2.candidate_entity_id,

            'S2',

            0, 0, 0, 0, 1

        FROM s1_tokens st

        INNER JOIN s2_token_freq f

            ON f.token = st.token

            AND f.df <= 1000

        INNER JOIN s2_tokens st2

            ON st2.token = st.token

            AND st2.country = st.country

        UNION ALL

        SELECT DISTINCT

            st.source1_entity_id,

            st3.candidate_entity_id,

            'S3',

            0, 0, 0, 0, 1

        FROM s1_tokens st

        INNER JOIN s3_token_freq f

            ON f.token = st.token

            AND f.df <= 1000

        INNER JOIN s3_tokens st3

            ON st3.token = st.token

            AND st3.country = st.country
        """
    )

    print(
        "Raw candidate rows:",
        count_table("candidate_pairs")
    )


    # ========================================================
    # CONSOLIDATE
    # ========================================================

    print_stage(
        "[4/7] Consolidating candidate passes"
    )

    print(
        "Deduplicating with disk spilling enabled..."
    )

    # This GROUP BY is the memory-heavy operation from the
    # previous version. With the explicit temp directory,
    # low thread count, and memory limit, DuckDB can spill
    # intermediate state to disk.

    con.execute(
        """
        CREATE TABLE consolidated_candidates AS

        SELECT

            source1_entity_id,

            candidate_entity_id,

            candidate_source,

            MAX(rule_exact_name)
                AS rule_exact_name,

            MAX(rule_prefix)
                AS rule_prefix,

            MAX(rule_postal_token)
                AS rule_postal_token,

            MAX(rule_house_token)
                AS rule_house_token,

            MAX(rule_rare_token)
                AS rule_rare_token,

            MAX(rule_exact_name)
            + MAX(rule_prefix)
            + MAX(rule_postal_token)
            + MAX(rule_house_token)
            + MAX(rule_rare_token)

                AS blocking_rules_matched

        FROM candidate_pairs

        GROUP BY

            source1_entity_id,

            candidate_entity_id,

            candidate_source
        """
    )

    consolidated_count = count_table(
        "consolidated_candidates"
    )

    print(
        f"Unique candidate pairs: {consolidated_count:,}"
    )


    # ========================================================
    # GROUND TRUTH
    # ========================================================

    print_stage(
        "[5/7] Building ground-truth pair table"
    )

    con.execute(
        f"""
        CREATE TABLE true_pairs AS

        SELECT DISTINCT

            source1_entity_id,

            trim(x) AS candidate_entity_id,

            CASE

                WHEN starts_with(
                    trim(x),
                    'S2-'
                )
                THEN 'S2'

                WHEN starts_with(
                    trim(x),
                    'S3-'
                )
                THEN 'S3'

                ELSE NULL

            END AS candidate_source

        FROM

        read_csv(
            '{GT}',
            delim='\\t',
            header=true,
            all_varchar=true,
            nullstr=''
        ) g

        CROSS JOIN LATERAL

        unnest(

            CASE

                WHEN
                    g.matched_entity_ids IS NULL
                    OR trim(
                        g.matched_entity_ids
                    ) = ''

                THEN []

                ELSE string_split(
                    g.matched_entity_ids,
                    ','
                )

            END

        ) AS u(x)

        WHERE
            trim(x) <> ''
        """
    )

    total_true = count_table(
        "true_pairs"
    )

    print(
        f"Total true pairs: {total_true:,}"
    )


    # ========================================================
    # LABEL CANDIDATES
    # ========================================================

    print_stage(
        "[6/7] Injecting labels and exporting"
    )

    # Instead of materializing another huge GROUP BY,
    # create the labeled table directly.

    con.execute(
        """
        CREATE TABLE labeled_candidates AS

        SELECT

            c.source1_entity_id,

            c.candidate_entity_id,

            c.candidate_source,

            c.rule_exact_name,

            c.rule_prefix,

            c.rule_postal_token,

            c.rule_house_token,

            c.rule_rare_token,

            c.blocking_rules_matched,

            CASE

                WHEN t.source1_entity_id IS NOT NULL

                THEN 1

                ELSE 0

            END AS label

        FROM consolidated_candidates c

        LEFT JOIN true_pairs t

            ON t.source1_entity_id =
               c.source1_entity_id

            AND t.candidate_entity_id =
                c.candidate_entity_id

            AND t.candidate_source =
                c.candidate_source
        """
    )


    total_candidates = count_table(
        "labeled_candidates"
    )

    positives = con.execute(
        """
        SELECT COUNT(*)
        FROM labeled_candidates
        WHERE label = 1
        """
    ).fetchone()[0]

    negatives = total_candidates - positives


    # ========================================================
    # EXPORT
    # ========================================================

    # Delete old output if present.

    if os.path.exists(OUTPUT_FILE):

        try:
            os.remove(OUTPUT_FILE)
        except PermissionError:

            raise RuntimeError(
                "Close anything using "
                "train_candidate_pairs_labeled.parquet "
                "and run again."
            )


    con.execute(
        f"""
        COPY labeled_candidates

        TO '{OUT}'

        (
            FORMAT PARQUET,

            COMPRESSION ZSTD,

            ROW_GROUP_SIZE 100000
        )
        """
    )


    # ========================================================
    # RECALL
    # ========================================================

    print_stage(
        "[7/7] Blocking recall evaluation"
    )

    recovered = con.execute(
        """
        SELECT COUNT(*)

        FROM true_pairs t

        INNER JOIN consolidated_candidates c

            ON c.source1_entity_id =
               t.source1_entity_id

            AND c.candidate_entity_id =
                t.candidate_entity_id

            AND c.candidate_source =
                t.candidate_source
        """
    ).fetchone()[0]


    missed = total_true - recovered

    recall = (
        recovered / total_true
        if total_true > 0
        else 0.0
    )


    # ========================================================
    # SOURCE-WISE RECALL
    # ========================================================

    source_stats = con.execute(
        """
        SELECT

            t.candidate_source,

            COUNT(*) AS true_pairs,

            COUNT(c.source1_entity_id)
                AS recovered

        FROM true_pairs t

        LEFT JOIN consolidated_candidates c

            ON c.source1_entity_id =
               t.source1_entity_id

            AND c.candidate_entity_id =
                t.candidate_entity_id

            AND c.candidate_source =
                t.candidate_source

        GROUP BY
            t.candidate_source

        ORDER BY
            t.candidate_source
        """
    ).fetchall()


    # ========================================================
    # FINAL STATISTICS
    # ========================================================

    print()
    print("=" * 80)

    print(
        f"Total True Pairs     : {total_true:,}"
    )

    print(
        f"Recovered True Pairs : {recovered:,}"
    )

    print(
        f"Missed True Pairs    : {missed:,}"
    )

    print(
        f"Blocking Recall Rate : {recall:.4%}"
    )

    print()
    print(
        f"Total Candidate Pairs: {total_candidates:,}"
    )

    print(
        f"Positives (Label 1)  : {positives:,}"
    )

    print(
        f"Negatives (Label 0)  : {negatives:,}"
    )

    print(
        f"Pos:Neg              : "
        f"1:{(negatives / positives):.2f}"
        if positives > 0
        else "Pos:Neg              : N/A"
    )

    print()
    print(
        "SOURCE-WISE RECALL"
    )

    print(
        "-" * 60
    )

    print(
        f"{'Source':<10}"
        f"{'Recovered':>15}"
        f"{'True':>15}"
        f"{'Recall':>15}"
    )

    print(
        "-" * 60
    )

    for source, true_count, recovered_count in source_stats:

        r = (
            recovered_count / true_count
            if true_count > 0
            else 0
        )

        print(
            f"{source:<10}"
            f"{recovered_count:>15,}"
            f"{true_count:>15,}"
            f"{r:>14.4%}"
        )


    print()
    print(
        f"OUTPUT: {OUTPUT_FILE}"
    )

    print()
    print(
        "=" * 80
    )

    if recall >= 0.98:

        print(
            "✅ BLOCKING TARGET ACHIEVED"
        )

    elif recall >= 0.95:

        print(
            "⚠️ BLOCKING RECALL >= 95%"
        )

    else:

        print(
            "⚠️ BLOCKING RECALL STILL BELOW TARGET"
        )

    print(
        "=" * 80
    )


    # ========================================================
    # CLOSE
    # ========================================================

    con.close()


if __name__ == "__main__":

    main()