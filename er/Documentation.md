# Business Entity Resolution — Methodology

## 1. Executive Summary

We resolve Source-2/3 business records to Source-1 reference entities with a four-stage pipeline:
country-agnostic normalization, **pair-of-rare-tokens blocking**, a LightGBM pairwise matcher, and a
**cluster-aware stage-2 decision model** that accepts or rejects each record's best candidate. Two insights
drive the result: (1) single tokens are massively reused in this data, but *pairs* of a record's rarest
tokens are highly selective, which gives 97% blocking recall with ~8 candidates per record; (2) the test set
contains far more "orphan" records (records whose business is absent from Source 1) than the training set,
so we train and tune under a simulated test-like orphan rate, which is what closed our validation-to-leaderboard gap.

## 2. Methodology

### 2.1 Problem Analysis (EDA)

| Fact | Train | Test |
|---|---|---|
| Source-1 entities | 2,206,821 | 1,732,544 |
| Source-2 + Source-3 records | 10,320,219 | 9,969,589 |
| Records per S1 entity | 4.7 | 5.8 |
| Countries | US, India | US, India, **France** |

Findings that shaped the design:

* **Every S2/S3 record matches at most one S1 entity** (7,638,365 true pairs, 7,638,365 distinct matched
  records). The task is therefore an *assignment* of each record to ≤ 1 entity, not free pairwise linking.
* 74% of train S2/S3 records have a match; 5.6% of S1 entities are singletons (no match).
* **Heavy token reuse**: e.g. 202 different S1 entities are named "Apex Inc"; street names and house numbers
  recur hundreds to thousands of times. Single-token blocking is either huge or low-recall.
* **Noise patterns**: native-script names (Devanagari, Bengali, Malayalam, Telugu), digit-for-letter typos
  (`P1atinum`, `Graysca1e`), accent injection (`Wórkshop`), website/handle names (`penatepioneervirtus.com`,
  `@haydenmozayyx`), word-order swaps, bracketed filler words (`[Center]`), shuffled address components,
  full vs abbreviated state names, house-number truncation (`6651` → `651`), missing addresses.

### 2.2 Solution Strategy

Blocking + classifier + cluster-aware decision layer. Core innovations: pair-key blocking, test-like
training distribution, and stage-2 cluster/anchor features.

## 3. Candidate Generation (Blocking)

* **Normalization** (`normalize.py`): Unidecode transliteration of any script, lowercase, `&`/`+` → "and",
  digit-for-letter repair inside alphanumeric tokens, repeated-letter collapse (`investtmentt` → `investment`,
  aligning transliterations with English), legal/filler-word-free "core" name, squashed core name (for
  website-style names), street/US-state/French-street abbreviation canonicalization. No logic is keyed on a
  specific country; `country` is an open string used only to scope blocking keys.
* **Pair-key index** (`blocking.py`): for each record take its 9 rarest tokens (name tokens, address tokens,
  squashed name), form all unordered pairs, hash each pair together with the country label. Keys shared by more
  than 60 S1 records are dropped. Each S2/S3 record is scored against every S1 record sharing ≥ 1 key by the
  summed IDF of shared keys; the **top 8** are kept.
* **Results (train, all 10.3M records)**: blocking recall **0.969–0.970** (share of true pairs present in
  candidates); 7.8 candidates per record, ~45 per S1 entity. Runtime ≈ 8–13 min on 4 CPU cores.
* An oracle that picks exactly the true pairs among these candidates would score macro F0.5 = **0.989**, so
  blocking costs ~1 point and the remaining gap is in the decision stages.

## 4. Matching Model

### Stage 1 — pairwise LightGBM (`features.py`, `train.py`)
45 features per (record, candidate):
* **Name**: RapidFuzz token-set / token-sort / partial / ratio on full name; Jaro-Winkler, ratio, partial,
  token-set on core name; ratio/partial on squashed name; token Jaccard; **consonant-skeleton** ratio and
  token-set (vowel-free, `ph→f`, `c/q→k`, `z→s`, `v→w`) for transliterated names; name lengths; S1 name frequency.
* **Address**: token-set / sort / ratio / partial; token-set without digits; house-number Jaccard,
  intersection count, first-number equality; number counts; empty-address flags.
* **Blocking context**: score, shared keys, rank, ratio and gap to the record's best candidate, candidate count.
* **Within-record relative features**: each similarity minus the best value among the record's candidates,
  plus is-best flags — targets "different businesses at the same address".
* **Meta**: source (S2/S3), non-ASCII name flag.

Training pairs come from blocking (hard negatives only). Validation is **grouped by S1 entity** (2 folds).

### Stage 2 — cluster-aware accept/reject (`stage2.py`)
Each record is tentatively assigned to its best stage-1 candidate. A second LightGBM decides whether to keep
it, using out-of-fold stage-1 probabilities plus:
* margin to the record's runner-up candidate;
* how many other records chose the same S1 entity and how confidently (count ≥ 0.5 / ≥ 0.9, max, mean, sum),
  this record's rank among them;
* **anchor features**: name/address similarity between this record and the two strongest *other* records
  assigned to the same S1 entity (a noisy variant often resembles a sibling variant more than the S1 record).

### Threshold selection
The stage-2 threshold is swept on out-of-fold predictions to maximize macro F0.5 (computed exactly as the
official metric, singletons included).

### Test-like training distribution
The test set has 5.8 records per S1 entity vs 4.7 in train, i.e. many more orphan records. We simulate this by
removing a random 20% of S1 entities from the training universe (their records become orphans), which yields
~45 candidates per S1 — matching test (44.8). Blocking, stage 1, stage 2 and thresholds are all trained and
tuned in this setting.

## 5. Results & Error Analysis

Held-out = S1 entities never used to train the scoring model (grouped 2-fold out-of-fold).

| Version | Validation setting | Macro F0.5 |
|---|---|---|
| Stage 1 only | original train | 0.9638 |
| + stage 2 | original train | 0.9692 |
| + anchor features | original train | 0.9714 (leaderboard: 0.961) |
| Stage 1 + stage 2 + anchors | **test-like** | 0.9671 |
| + skeleton & relative features | **test-like** | **0.9691** |

Final model (test-like validation): macro precision 0.983, macro recall 0.938, pair precision 0.991,
pair recall 0.937.

**Common false positives**: different businesses at the same address with overlapping name tokens
(`Hitech Lotus Impex` vs `Haitek Lots Knslting` at the same Delhi address); website-style names at a
shared address; family-name businesses at the same street.

**Common false negatives**: records with no address and a very common name (dozens of identical S1 names);
transliterated names whose transliteration diverges strongly; truncated/incorrect house numbers combined with
name typos.

## 6. Conclusion

Pair-key blocking makes a 10M × 1.7M problem tractable on a 4-core machine with ~97% recall, and a
cluster-aware second stage converts the structure of the problem (each record belongs to at most one entity;
real entities appear in several sources) into precision. The biggest single lesson was that the validation
distribution must match the test's orphan rate; reproducing it realigned validation with the leaderboard.

## 7. Appendix — Reproduce

```bash
pip install -r requirements.txt
python src/normalize.py dataset work
python -c "import polars as pl, numpy as np; s=pl.read_parquet('work/train_source1.parquet'); \
  s.filter(pl.Series(np.random.default_rng(42).random(s.height) >= 0.20)).write_parquet('work/trainsim_source1.parquet')"
cp work/train_source2.parquet work/trainsim_source2.parquet
cp work/train_source3.parquet work/trainsim_source3.parquet
python src/run_block.py work trainsim 8
python src/run_block.py work test 8
SPLIT=trainsim python src/train.py work dataset 8
SPLIT=trainsim python src/stage2.py train work dataset
python src/predict.py work output
SPLIT=trainsim python src/stage2.py apply work output
python utils/validate_submission.py --matching output/matching_results.tsv \
  --candidate output/candidate_pairs.tsv --test-dir dataset/test
```

Libraries (all open source, no pretrained models, no external data or APIs): polars, numpy, LightGBM (MIT),
RapidFuzz (MIT), Unidecode (GPL-2.0, used only for text transliteration), pyarrow.
