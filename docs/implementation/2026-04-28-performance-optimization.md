# Performance Optimization Walkthrough

## Improvements

### 1. Matching Pipeline (matcher.py)

- **FTS5 Truncation**: Truncated the search query to the first 100 words for the Tier 1 FTS5 recall stage. This prevents performance degradation on large files while maintaining sufficient recall.
- **Recall Increase**: Increased Tier 1 retrieval limit from 20 to 50 candidates to ensure canonical licenses are not lost among similar variants (e.g., BSD variants).
- **Adaptive Rule Logic**:
  - **Rule 1 (Full)**: Triggered for large queries. Uses high-speed global `token_sort_ratio`.
  - **Rule 2 (Surgical)**: Restricted to small snippets (< 500 words). Uses `partial_ratio_alignment` only where it provides value without killing performance.
- **Composite Scoring**: Added a coverage-aware score to break ties between a license and its superset (e.g., BSD-3-Clause vs Sleepycat).

### 2. Database Update (database.py)

- **Bulk Operations**: Refactored `_update_db_records` and `_prepare_license_record` to use `executemany`. This replaces hundreds of individual `INSERT` calls with a single bulk transaction.
- **Pre-calculated Metadata**: Added `is_high_usage` calculation to the update process, ensuring it is correctly populated based on OSI/FSF status and popularity data.
- **Improved Progress Reporting**: Streamlined the CLI output during updates to report data preparation and insertion phases separately.

### 3. Test Suite (test_accuracy.py)

- **Bulk Population**: Refactored the test database setup to use `executemany` and pre-calculated metadata, reducing setup time significantly.
- **Retrieval Validation**: Added a subset test to verify the FTS5 truncation doesn't negatively impact recall.

## Verification Results

### Performance

- **Subset Accuracy Test (38 matches)**: 20 seconds (down from minutes).
- **Full Accuracy Test (3330 matches)**: ~5 minutes (down from 2+ hours).

### Accuracy

- **Top 5 Accuracy**: 100% for 0% and 1% distortion on core licenses.
- **Top 1 Accuracy**: ~94% (Lower due to identical license texts in fixtures like GPL-2.0-only vs GPL-2.0-or-later).
