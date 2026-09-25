import os
import duckdb

# ============================================================
# CONFIG
# ============================================================

BASE = r"C:\Users\BIT\amazonml"
FEATURE_DIR = os.path.join(BASE, "features")

CANDIDATES = os.path.join(FEATURE_DIR, "train_candidate_pairs_labeled.parquet")
GROUND_TRUTH = os.path.join(BASE, "data", "raw", "train", "train_ground_truth.tsv")

S1_FILE = os.path.join(FEATURE_DIR, "train_s1_cd.parquet")
S2_FILE = os.path.join(FEATURE_DIR, "train_s2_cd.parquet")
S3_FILE = os.path.join(FEATURE_DIR, "train_s3_cd.parquet")


def sql_path(path: str) -> str:
    return path.replace("\\", "/").replace("'", "''")


cand = sql_path(CANDIDATES)
gt = sql_path(GROUND_TRUTH)
s1_p = sql_path(S1_FILE)
s2_p = sql_path(S2_FILE)
s3_p = sql_path(S3_FILE)

con = duckdb.connect()
con.execute("PRAGMA threads=8;")
con.execute("PRAGMA preserve_insertion_order=false;")

print("\n" + "=" * 90)
print("FAST BLOCKING RECALL & ERROR DIAGNOSTICS")
print("=" * 90)

# ============================================================
# 1. LOAD GROUND TRUTH & CANDIDATES
# ============================================================

print("\n[1/4] Parsing ground truth and indexing generated candidates...")

con.execute(f"""
    CREATE OR REPLACE TEMP VIEW gt_raw AS
    SELECT source1_entity_id, matched_entity_ids
    FROM read_csv(
        '{gt}',
        delim='\\t',
        header=true,
        all_varchar=true,
        nullstr=''
    );
""")

con.execute("""
    CREATE OR REPLACE TEMP TABLE true_pairs AS
    SELECT DISTINCT
        g.source1_entity_id,
        trim(x) AS candidate_entity_id,
        CASE
            WHEN starts_with(trim(x), 'S2-') THEN 'S2'
            WHEN starts_with(trim(x), 'S3-') THEN 'S3'
            ELSE NULL
        END AS candidate_source
    FROM gt_raw g,
    LATERAL unnest(
        CASE
            WHEN g.matched_entity_ids IS NULL OR trim(g.matched_entity_ids) = '' THEN []
            ELSE string_split(g.matched_entity_ids, ',')
        END
    ) AS u(x)
    WHERE trim(x) <> '';
""")

# Load candidates table
con.execute(f"""
    CREATE OR REPLACE TEMP VIEW candidates AS
    SELECT
        source1_entity_id,
        candidate_entity_id,
        candidate_source,
        label,
        blocking_rules_matched
    FROM read_parquet('{cand}');
""")

# ============================================================
# 2. SINGLE-PASS RECOVERY EVALUATION TABLE
# ============================================================
# Joins ONCE and caches results for global recall, source recall, and error slicing

print("[2/4] Executing unified coverage join...")

con.execute("""
    CREATE OR REPLACE TEMP TABLE eval_joined AS
    SELECT
        t.source1_entity_id,
        t.candidate_entity_id,
        t.candidate_source,
        CASE WHEN c.source1_entity_id IS NOT NULL THEN 1 ELSE 0 END AS is_recovered,
        c.blocking_rules_matched
    FROM true_pairs t
    LEFT JOIN candidates c
      ON c.source1_entity_id = t.source1_entity_id
     AND c.candidate_entity_id = t.candidate_entity_id
     AND c.candidate_source = t.candidate_source;
""")

# ============================================================
# 3. METRICS AGGREGATION & REDUCTION RATIO
# ============================================================

print("[3/4] Aggregating evaluation statistics...\n")

total_true = con.execute("SELECT COUNT(*) FROM true_pairs;").fetchone()[0]
total_candidates = con.execute("SELECT COUNT(*) FROM candidates;").fetchone()[0]
recovered = con.execute("SELECT SUM(is_recovered) FROM eval_joined;").fetchone()[0] or 0

missed = total_true - recovered
recall = (recovered / total_true) if total_true > 0 else 0.0

# Calculate Search Space Reduction Ratio (RR)
s1_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{s1_p}');").fetchone()[0]
s2_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{s2_p}');").fetchone()[0]
s3_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{s3_p}');").fetchone()[0]
cartesian_space = s1_count * (s2_count + s3_count)
reduction_ratio = 1.0 - (total_candidates / cartesian_space) if cartesian_space > 0 else 0.0

print("=" * 90)
print("BLOCKING EVALUATION METRICS")
print("=" * 90)
print(f"Total Ground Truth Matches : {total_true:,}")
print(f"Total Candidates Generated : {total_candidates:,}")
print(f"True Pairs Recovered       : {recovered:,}")
print(f"True Pairs Missed          : {missed:,}")
print(f"Blocking Recall            : {recall:.6%}")
print(f"Cartesian Search Space     : {cartesian_space:,}")
print(f"Reduction Ratio (RR)       : {reduction_ratio:.6%}")

# Source-wise breakdown
print("\n" + "-" * 50)
print(f"{'Source':<10} | {'Recovered':<12} | {'Total True':<12} | {'Recall':<10}")
print("-" * 50)

source_stats = con.execute("""
    SELECT
        candidate_source,
        SUM(is_recovered) AS rec,
        COUNT(*) AS total
    FROM eval_joined
    GROUP BY candidate_source
    ORDER BY candidate_source;
""").fetchall()

for src, rec, tot in source_stats:
    rec_val = rec or 0
    src_rec = (rec_val / tot) if tot > 0 else 0.0
    print(f"{src:<10} | {rec_val:<12,} | {tot:<12,} | {src_rec:.4%}")
print("-" * 50)

# ============================================================
# 4. DIAGNOSTIC ROOT-CAUSE ANALYSIS OF MISSED PAIRS
# ============================================================

print("\n[4/4] Diagnosing top missed true pairs (comparing strings & tokens)...")

# Cache unified reference view for quick feature join
con.execute(f"""
    CREATE OR REPLACE TEMP TABLE source_entities AS
    SELECT entity_id, canonical_name, canonical_address, postal_code FROM read_parquet('{s1_p}')
    UNION ALL
    SELECT entity_id, canonical_name, canonical_address, postal_code FROM read_parquet('{s2_p}')
    UNION ALL
    SELECT entity_id, canonical_name, canonical_address, postal_code FROM read_parquet('{s3_p}');
""")

missed_diagnostics = con.execute("""
    SELECT
        m.source1_entity_id,
        s1.canonical_name AS s1_name,
        s1.postal_code AS s1_zip,
        m.candidate_entity_id,
        cand.canonical_name AS cand_name,
        cand.postal_code AS cand_zip
    FROM (
        SELECT source1_entity_id, candidate_entity_id 
        FROM eval_joined 
        WHERE is_recovered = 0 
        LIMIT 10
    ) m
    LEFT JOIN source_entities s1 ON s1.entity_id = m.source1_entity_id
    LEFT JOIN source_entities cand ON cand.entity_id = m.candidate_entity_id;
""").fetchall()

if missed_diagnostics:
    print("\nSAMPLE MISSED PAIR AUDIT:")
    for row in missed_diagnostics:
        print(f"• S1   [{row[0]}]: '{row[1]}' (ZIP: {row[2]})")
        print(f"  CAND [{row[3]}]: '{row[4]}' (ZIP: {row[5]})")
        print("  " + "-" * 70)
else:
    print("No missed pairs found in sample!")

# ============================================================
# VERDICT
# ============================================================

print("\n" + "=" * 90)
if recall >= 0.98:
    print("✅ BLOCKING TARGET ACHIEVED (>= 98%) — Proceed to Stage 2 (Feature Engineering / ML)")
elif recall >= 0.95:
    print("⚠️ WARNING: BLOCKING RECALL BETWEEN 95% AND 98% — Consider adding phonetic blocking (Double Metaphone / N-grams)")
else:
    print("❌ CRITICAL: RECALL BELOW 95% — High downstream error floor. Do not train matcher yet.")
print("=" * 90 + "\n")

con.close()