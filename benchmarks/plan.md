# License Identification Performance Benchmark Plan

This document outlines the plan for benchmarking the license identification pipeline, specifically comparing the performance of the current `license-marker` branch against the `main` branch. 

The goal is to determine if the introduction of the license marker detection improves accuracy (precision/recall) and to measure its impact on speed and memory consumption. This data will inform future decisions regarding integration, triggering thresholds, early returns, and window sizes.

## 1. Objectives

Evaluate the performance of license detection across two branches (`license-marker` and `main`) on five key metrics:
1. **Recall:** The fraction of relevant licenses that are successfully identified.
2. **Precision:** The fraction of identified licenses that are correct.
3. **Speed (Wall Time):** The total elapsed time for processing queries.
4. **Memory Peak:** The maximum memory allocated during the benchmark.
5. **Memory Average:** The average memory usage over the execution time.

## 2. Input Data & Queries

The benchmark will utilize the test fixtures already present in the `license-marker` branch (e.g., under `tests/fixtures/license-data` and `tests/fixtures/license-markers`).

Queries will be categorized into five distinct input types to test different aspects of the detection pipeline:
1. **License ID:** Exact and case-insensitive SPDX License IDs.
2. **License Name:** Exact and partial license names.
3. **Short License Text:** Snippets and truncated license texts.
4. **Long License Text (Near Complete):** Full or nearly full license texts.
5. **Mixed Content:** Source code or documentation containing embedded license information (IDs, names, or text fragments).

**Expected Output:** SPDX License ID or a full SPDX License Expression.

## 3. Architecture & Scripts

To ensure clean execution and avoid import/SQLite conflicts between the branches, the benchmark will be divided into two scripts:

### 3.1 `bench_single.py`
- Responsible for running the benchmark on a single branch.
- **Execution:** Checked out to the target branch.
- **Data Setup:** 
  - Downloads all necessary license metadata/data.
  - Caches the downloaded data to avoid repeated network requests.
  - Initializes an in-memory SQLite database.
  - The database name will use the format: `{test_name}_{uuid}` to ensure complete isolation and prevent clashes.
  - Ensures the correct schema and data required for the specific branch are loaded.
- **Measurement:** 
- Uses `time.monotonic()` (or `perf_counter()`) for wall time.
  - Uses `tracemalloc` for peak memory tracking and to potentially pinpoint hot/cold paths.
- **Output:** Writes results as a JSON file to `benchmarks/outputs/`.
  - Filename format: `{benchmark_name}_{branch_name}_{YYYYMMDD_HHMMSS}.json`

### 3.2 `bench_compare.py`
- Responsible for orchestrating the benchmark and generating the final comparison report.
- **Branch Checkout:** Uses `subprocess` to explicitly check out the target branches (`main` and `license-marker`) before running the single script.
- **Process Isolation:** Uses `subprocess` to call `bench_single.py` sequentially.
  - **Step 1:** Checkout `main` branch -> run `bench_single.py` -> save JSON.
  - **Step 2:** Checkout `license-marker` branch -> run `bench_single.py` -> save JSON.
- **Analysis:** Reads the generated JSON files from `benchmarks/outputs/` and computes the diffs for recall, precision, speed, and memory.
- **Output:** Prints a human-readable summary and analysis, and writes the summary to `benchmarks/`.

## 4. Execution Rules

- **No Parallelism:** Tests will be run strictly in sequence to avoid resource contention and maintain accurate timing/memory measurements.
- **Fairness:** The `license-marker` branch's test fixtures and, where possible, test case code will be used across both runs to ensure apples-to-apples comparison.
- **Deterministic:** The same seed or randomized order (if any) will be applied consistently.

## 5. Output Artifacts

- **Raw Data:** JSON files stored in `benchmarks/outputs/`.
- **Summary Report:** Markdown files stored in `benchmarks/` containing human-readable matrices indicating areas of improvement or degradation.
