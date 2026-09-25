import duckdb
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

S1 = BASE / "data" / "raw" / "train" / "train_source1.tsv"
S2 = BASE / "data" / "raw" / "train" / "train_source2.tsv"
S3 = BASE / "data" / "raw" / "train" / "train_source3.tsv"
GT = BASE / "data" / "raw" / "train" / "train_ground_truth.tsv"

con = duckdb.connect()

# ---------------------------------------------------------
# Helper: read a TSV
# ---------------------------------------------------------
def read_table(path):
    return f"""
        read_csv(
            '{path}',
            delim='\\t',
            header=true,
            all_varchar=true
        )
    """


# ---------------------------------------------------------
# 1. Inspect ZERO-MATCH entities
# ---------------------------------------------------------
print("=" * 80)
print("1. ZERO-MATCH EXAMPLES")
print("=" * 80)

query = f"""
SELECT
    s1.entity_id,
    s1.business_name,
    s1.business_address,
    s1.country
FROM {read_table(S1)} s1
JOIN {read_table(GT)} gt
    ON s1.entity_id = gt.source1_entity_id
WHERE gt.matched_entity_ids IS NULL
   OR TRIM(gt.matched_entity_ids) = ''
LIMIT 20;
"""

for row in con.execute(query).fetchall():
    print(row)


# ---------------------------------------------------------
# 2. Inspect SINGLE-MATCH entities
# ---------------------------------------------------------
print("\n" + "=" * 80)
print("2. SINGLE-MATCH EXAMPLES")
print("=" * 80)

query = f"""
SELECT
    s1.entity_id,
    s1.business_name,
    s1.business_address,
    s1.country,
    gt.matched_entity_ids
FROM {read_table(S1)} s1
JOIN {read_table(GT)} gt
    ON s1.entity_id = gt.source1_entity_id
WHERE gt.matched_entity_ids IS NOT NULL
  AND TRIM(gt.matched_entity_ids) <> ''
  AND ARRAY_LENGTH(STRING_SPLIT(gt.matched_entity_ids, ',')) = 1
LIMIT 20;
"""

for row in con.execute(query).fetchall():
    print(row)


# ---------------------------------------------------------
# 3. Inspect MULTI-MATCH entities
# ---------------------------------------------------------
print("\n" + "=" * 80)
print("3. MULTI-MATCH EXAMPLES")
print("=" * 80)

query = f"""
SELECT
    s1.entity_id,
    s1.business_name,
    s1.business_address,
    s1.country,
    gt.matched_entity_ids
FROM {read_table(S1)} s1
JOIN {read_table(GT)} gt
    ON s1.entity_id = gt.source1_entity_id
WHERE gt.matched_entity_ids IS NOT NULL
  AND TRIM(gt.matched_entity_ids) <> ''
  AND ARRAY_LENGTH(STRING_SPLIT(gt.matched_entity_ids, ',')) >= 3
LIMIT 20;
"""

for row in con.execute(query).fetchall():
    print(row)


# ---------------------------------------------------------
# 4. Show actual matched records from Source 2
# ---------------------------------------------------------
print("\n" + "=" * 80)
print("4. S1 + ACTUAL S2 MATCHES")
print("=" * 80)

query = f"""
WITH sample AS (
    SELECT
        source1_entity_id,
        STRING_SPLIT(matched_entity_ids, ',')[1] AS s2_id
    FROM {read_table(GT)}
    WHERE matched_entity_ids IS NOT NULL
      AND TRIM(matched_entity_ids) <> ''
    LIMIT 10
)
SELECT
    s1.entity_id AS s1_id,
    s1.business_name AS s1_name,
    s1.business_address AS s1_address,
    s2.entity_id AS s2_id,
    s2.business_name AS s2_name,
    s2.business_address AS s2_address,
    s1.country
FROM sample x
JOIN {read_table(S1)} s1
    ON s1.entity_id = x.source1_entity_id
JOIN {read_table(S2)} s2
    ON s2.entity_id = x.s2_id;
"""

for row in con.execute(query).fetchall():
    print("\n", row)


# ---------------------------------------------------------
# 5. Same thing for Source 3
# ---------------------------------------------------------
print("\n" + "=" * 80)
print("5. S1 + ACTUAL S3 MATCHES")
print("=" * 80)

query = f"""
WITH sample AS (
    SELECT
        source1_entity_id,
        STRING_SPLIT(matched_entity_ids, ',')[1] AS s3_id
    FROM {read_table(GT)}
    WHERE matched_entity_ids IS NOT NULL
      AND TRIM(matched_entity_ids) <> ''
    LIMIT 10
)
SELECT
    s1.entity_id AS s1_id,
    s1.business_name AS s1_name,
    s1.business_address AS s1_address,
    s3.entity_id AS s3_id,
    s3.business_name AS s3_name,
    s3.business_address AS s3_address,
    s1.country
FROM sample x
JOIN {read_table(S1)} s1
    ON s1.entity_id = x.source1_entity_id
JOIN {read_table(S3)} s3
    ON s3.entity_id = x.s3_id;
"""

for row in con.execute(query).fetchall():
    print("\n", row)


print("\n" + "=" * 80)
print("INSPECTION COMPLETE")
print("=" * 80)

con.close()