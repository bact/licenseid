# Implementation Plan: Comprehensive Benchmark Suite

This plan details how we will update `benchmarks/bench_single.py` and `benchmarks/bench_compare.py` to evaluate the pipeline's performance across all 5 generated input types (License IDs, Names, Short Texts, Long Texts, and Mixed Content).

## Proposed Changes

### 1. Database Initialization

- `bench_single.py` will continue to read from `tests/fixtures/license-text-long/*.json` (Type 4) to populate the in-memory SQLite database, as this directory contains the complete metadata and full texts required for indexing.

### 2. Expanding `bench_single.py` to Test All Types

The evaluation loop will be expanded to sequentially process all 5 input types and maintain separate statistics for each.

- **Type 1 (License IDs)**: Read `tests/fixtures/license-id/license_ids.json`. For each object, iterate through the `variations` array. The expected match is `canonical_id`.
- **Type 2 (License Names)**: Read `tests/fixtures/license-name/license_names.json`. Iterate through the name fields (`name_verbatim`, `name_space`, `name_casing`, `name_punct`, `name_distored`).
- **Type 3 (Short Text)**: Iterate through `tests/fixtures/license-text-short/*.json`. For each file, extract the `license_id` and evaluate every value whose key starts with `license_text_short_`.
- **Type 4 (Long Text)**: Iterate through `tests/fixtures/license-text-long/*.json`. Test the clean `license_text` alongside all available distortion rates (e.g., 01, 02, 05, 10, 20).
- **Type 5 (Mixed Content)**: Traverse `tests/fixtures/mixed-content/`. For every canonical ID directory, read every contained file (e.g., `README.md`, `package.json`, `.py`) and run it through the matcher.

### 3. Statistics Aggregation

The `stats` dictionary will become nested: `stats[input_type][sub_category]`.

- For example, Type 4 stats will track `stats["type_4"]["distorted_05"]`.
- Type 1 will track `stats["type_1"]["variations"]`.
- Each sub-category will track `total`, `top1`, `top3`, `top5`.

### 4. Updating `bench_compare.py`

- Modify the `generate_markdown_report` function to iterate over the new nested `stats` dictionary.
- Output categorized markdown tables for each Input Type, cleanly showing Recall@1, Recall@3, and Recall@5 for each sub-category or distortion rate.

### 5. Verification Mode

- As requested, I will implement a `--verify` flag (or temporarily hardcode a limit) in `bench_single.py` to restrict testing to just **1 or 2 items per input type**.
- This will allow us to run a lightning-fast validation of the code syntax and structure without executing thousands of queries.

## User Review Required
>
> [!IMPORTANT]
> Please review this benchmark expansion plan. I will not implement or run the full benchmark until you give the go-ahead. Does this structure meet your expectations for the detailed comparison?
