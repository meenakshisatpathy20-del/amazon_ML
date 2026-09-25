import duckdb

# ============================================================
# GROUND TRUTH ANALYSIS
# Amazon Business Entity Resolution
# ============================================================

con = duckdb.connect()

TRAIN_DIR = "data/raw/train"

S1 = f"{TRAIN_DIR}/train_source1.tsv"
GT = f"{TRAIN_DIR}/train_ground_truth.tsv"


def read_csv(file):
    return f"""
        read_csv(
            '{file}',
            delim = '\t',
            header = true,
            all_varchar = true
        )
    """


print("=" * 80)
print("GROUND TRUTH ANALYSIS")
print("=" * 80)


# ============================================================
# 1. MATCH COUNT PER SOURCE-1 ENTITY
# ============================================================

print("\n1. MATCH COUNT DISTRIBUTION")
print("-" * 80)

query = f"""
WITH match_counts AS (
    SELECT
        source1_entity_id,

        CASE
            WHEN matched_entity_ids IS NULL
                 OR TRIM(matched_entity_ids) = ''
            THEN 0

            ELSE LENGTH(matched_entity_ids)
                 - LENGTH(REPLACE(matched_entity_ids, ',', ''))
                 + 1
        END AS match_count

    FROM {read_csv(GT)}
)

SELECT
    match_count,
    COUNT(*) AS s1_entities,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS percentage

FROM match_counts

GROUP BY match_count
ORDER BY match_count;
"""

rows = con.execute(query).fetchall()

print(f"{'Matches':>10} {'S1 Entities':>20} {'Percentage':>15}")
print("-" * 50)

for match_count, entities, percentage in rows:
    print(
        f"{match_count:>10} "
        f"{entities:>20,} "
        f"{percentage:>14.2f}%"
    )


# ============================================================
# 2. ZERO / ONE / MULTIPLE MATCHES
# ============================================================

print("\n2. ZERO / SINGLE / MULTIPLE MATCHES")
print("-" * 80)

query = f"""
WITH match_counts AS (
    SELECT
        CASE
            WHEN matched_entity_ids IS NULL
                 OR TRIM(matched_entity_ids) = ''
            THEN 0

            ELSE LENGTH(matched_entity_ids)
                 - LENGTH(REPLACE(matched_entity_ids, ',', ''))
                 + 1
        END AS match_count

    FROM {read_csv(GT)}
)

SELECT
    SUM(CASE WHEN match_count = 0 THEN 1 ELSE 0 END) AS zero_matches,

    SUM(CASE WHEN match_count = 1 THEN 1 ELSE 0 END) AS one_match,

    SUM(CASE WHEN match_count >= 2 THEN 1 ELSE 0 END) AS multiple_matches,

    COUNT(*) AS total

FROM match_counts;
"""

zero_matches, one_match, multiple_matches, total = con.execute(query).fetchone()

print(f"Zero matches:       {zero_matches:,}")
print(f"Exactly one match:  {one_match:,}")
print(f"Multiple matches:   {multiple_matches:,}")
print(f"Total S1 entities:  {total:,}")


# ============================================================
# 3. COUNT S2 VS S3 MATCHES
# ============================================================

print("\n3. S2 VS S3 MATCH COUNTS")
print("-" * 80)

query = f"""
WITH exploded AS (

    SELECT
        source1_entity_id,
        TRIM(match_id) AS match_id

    FROM {read_csv(GT)},
    UNNEST(
        CASE
            WHEN matched_entity_ids IS NULL
                 OR TRIM(matched_entity_ids) = ''
            THEN []
            ELSE STRING_SPLIT(matched_entity_ids, ',')
        END
    ) AS t(match_id)
)

SELECT
    SUM(
        CASE
            WHEN match_id LIKE 'S2-%'
            THEN 1
            ELSE 0
        END
    ) AS s2_matches,

    SUM(
        CASE
            WHEN match_id LIKE 'S3-%'
            THEN 1
            ELSE 0
        END
    ) AS s3_matches,

    COUNT(*) AS total_matches

FROM exploded;
"""

s2_matches, s3_matches, total_matches = con.execute(query).fetchone()

print(f"S2 matches:    {s2_matches:,}")
print(f"S3 matches:    {s3_matches:,}")
print(f"Total matches: {total_matches:,}")


# ============================================================
# 4. S1 ENTITIES HAVING S2 AND/OR S3
# ============================================================

print("\n4. MATCH SOURCE COMBINATION")
print("-" * 80)

query = f"""
WITH exploded AS (

    SELECT
        source1_entity_id,
        TRIM(match_id) AS match_id

    FROM {read_csv(GT)},
    UNNEST(
        CASE
            WHEN matched_entity_ids IS NULL
                 OR TRIM(matched_entity_ids) = ''
            THEN []
            ELSE STRING_SPLIT(matched_entity_ids, ',')
        END
    ) AS t(match_id)
),

classified AS (

    SELECT
        source1_entity_id,

        MAX(
            CASE
                WHEN match_id LIKE 'S2-%'
                THEN 1 ELSE 0
            END
        ) AS has_s2,

        MAX(
            CASE
                WHEN match_id LIKE 'S3-%'
                THEN 1 ELSE 0
            END
        ) AS has_s3

    FROM exploded

    GROUP BY source1_entity_id
)

SELECT
    CASE
        WHEN has_s2 = 1 AND has_s3 = 1
            THEN 'S2 + S3'

        WHEN has_s2 = 1 AND has_s3 = 0
            THEN 'S2 only'

        WHEN has_s2 = 0 AND has_s3 = 1
            THEN 'S3 only'

        ELSE 'No match'
    END AS match_type,

    COUNT(*) AS s1_entities

FROM classified

GROUP BY match_type

ORDER BY s1_entities DESC;
"""

rows = con.execute(query).fetchall()

for match_type, count in rows:
    print(f"{match_type:<15} {count:>15,}")


# ============================================================
# 5. CHECK INVALID MATCH ID PREFIXES
# ============================================================

print("\n5. INVALID MATCH IDS")
print("-" * 80)

query = f"""
WITH exploded AS (

    SELECT
        TRIM(match_id) AS match_id

    FROM {read_csv(GT)},
    UNNEST(
        CASE
            WHEN matched_entity_ids IS NULL
                 OR TRIM(matched_entity_ids) = ''
            THEN []
            ELSE STRING_SPLIT(matched_entity_ids, ',')
        END
    ) AS t(match_id)
)

SELECT
    COUNT(*)

FROM exploded

WHERE match_id NOT LIKE 'S2-%'
  AND match_id NOT LIKE 'S3-%';
"""

invalid = con.execute(query).fetchone()[0]

print(f"Invalid S2/S3 IDs: {invalid:,}")


# ============================================================
# 6. CHECK S1 COUNTRY VS MATCH COUNT
# ============================================================

print("\n6. MATCH COUNT BY S1 COUNTRY")
print("-" * 80)

query = f"""
WITH gt_counts AS (

    SELECT
        source1_entity_id,

        CASE
            WHEN matched_entity_ids IS NULL
                 OR TRIM(matched_entity_ids) = ''
            THEN 0

            ELSE LENGTH(matched_entity_ids)
                 - LENGTH(REPLACE(matched_entity_ids, ',', ''))
                 + 1
        END AS match_count

    FROM {read_csv(GT)}
)

SELECT
    s1.country,

    COUNT(*) AS s1_entities,

    SUM(
        CASE
            WHEN gt_counts.match_count = 0
            THEN 1 ELSE 0
        END
    ) AS zero_matches,

    ROUND(
        AVG(gt_counts.match_count),
        2
    ) AS avg_matches

FROM gt_counts

JOIN {read_csv(S1)} s1
    ON gt_counts.source1_entity_id = s1.entity_id

GROUP BY s1.country

ORDER BY s1.country;
"""

rows = con.execute(query).fetchall()

print(
    f"{'Country':<15}"
    f"{'S1 Entities':>18}"
    f"{'Zero Matches':>18}"
    f"{'Avg Matches':>18}"
)

print("-" * 70)

for country, entities, zero, avg_matches in rows:
    print(
        f"{country:<15}"
        f"{entities:>18,}"
        f"{zero:>18,}"
        f"{avg_matches:>18.2f}"
    )


# ============================================================
# FINISH
# ============================================================

print("\n" + "=" * 80)
print("GROUND TRUTH ANALYSIS COMPLETE")
print("=" * 80)

con.close()