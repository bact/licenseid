#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Single-branch benchmark: recall, precision, speed, memory.

Usage:
    python bench_single.py <src_path> <label> <benchmark_name> <timestamp> [--verify]

Outputs JSON to stdout and to benchmarks/outputs/.
Runs completely standalone — no shared state.
"""

import json
import sqlite3
import sys
import time
import tracemalloc
import uuid
from pathlib import Path
from typing import Any

if len(sys.argv) < 5:
    print(
        "Usage: python bench_single.py <src_path> <label> <benchmark_name> <timestamp> [--verify]"
    )
    sys.exit(1)

SRC_PATH: str = sys.argv[1]
LABEL: str = sys.argv[2]
BENCHMARK_NAME: str = sys.argv[3]
TIMESTAMP: str = sys.argv[4]
IS_VERIFY: bool = "--verify" in sys.argv

FIXTURES_DIR: Path = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "license-text-long"
)

sys.path.insert(0, SRC_PATH)
# pylint: disable=wrong-import-position
from licenseid.database import LicenseDatabase  # noqa: E402
from licenseid.matcher import AggregatedLicenseMatcher  # noqa: E402
from licenseid.normalize import normalize_text  # noqa: E402


def init_stat() -> dict[str, int]:
    return {"total": 0, "top1": 0, "top3": 0, "top5": 0}


def check_match(
    true_id: str,
    text: str,
    matcher: Any,
    stat_obj: dict[str, int],
    failures_list: list[dict[str, Any]],
    category: str,
    subcat: str,
    global_counts: dict[str, int],
) -> None:
    results = matcher.match(text)
    matched_ids = [r["license_id"] for r in results]

    stat_obj["total"] += 1
    global_counts["total_returned"] += len(matched_ids)
    global_counts["correct_returned"] += sum(1 for lid in matched_ids if lid == true_id)

    if matched_ids and matched_ids[0] == true_id:
        stat_obj["top1"] += 1
    else:
        failures_list.append(
            {
                "cat": category,
                "subcat": subcat,
                "true": true_id,
                "got": matched_ids[0] if matched_ids else "NONE",
            }
        )

    if true_id in matched_ids[:3]:
        stat_obj["top3"] += 1
    if true_id in matched_ids[:5]:
        stat_obj["top5"] += 1


def main() -> None:
    # pylint: disable=too-many-locals,too-many-statements
    fixtures: list[Path] = sorted(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        print(json.dumps({"error": f"No fixtures in {FIXTURES_DIR}"}))
        sys.exit(1)

    print(
        f"[{LABEL}] {len(fixtures)} DB source fixtures, building DB …",
        file=sys.stderr,
        flush=True,
    )

    db_name: str = f"bench_{LABEL}_{uuid.uuid4().hex}"
    db_path: str = f"file:{db_name}?mode=memory&cache=shared"

    db_manager = LicenseDatabase(db_path)
    _ = db_manager

    to_insert_licenses: list[tuple[Any, ...]] = []
    to_insert_index: list[tuple[str, str]] = []

    safe_to_canon: dict[str, str] = {}

    for fp in fixtures:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        normalized = normalize_text(data["license_text"])
        word_count = len(normalized.split())
        c_id = data["license_id"]
        to_insert_licenses.append(
            (
                c_id,
                data.get("name", ""),
                data.get("is_spdx", True),
                data.get("is_osi_approved", False),
                data.get("is_fsf_libre", False),
                data.get("is_high_usage", False),
                data.get("is_deprecated", False),
                data.get("superseded_by"),
                data.get("pop_score", 1),
                word_count,
            )
        )
        to_insert_index.append((c_id, normalized))
        safe_to_canon[c_id.replace(" ", "_").replace("/", "_")] = c_id

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("BEGIN TRANSACTION")
        try:
            # Dynamically get columns for backward compatibility with 'main' branch
            cursor = conn.execute("PRAGMA table_info(licenses)")
            columns = [row[1] for row in cursor.fetchall()]

            # Map available columns to their values from the tuple
            # Tuple: (license_id, name, is_spdx, is_osi_approved, is_fsf_libre,
            #         is_high_usage, is_deprecated, superseded_by, pop_score, word_count)
            all_cols = [
                "license_id",
                "name",
                "is_spdx",
                "is_osi_approved",
                "is_fsf_libre",
                "is_high_usage",
                "is_deprecated",
                "superseded_by",
                "pop_score",
                "word_count",
            ]

            insert_cols = [c for c in all_cols if c in columns]
            col_indices = [all_cols.index(c) for c in insert_cols]

            filtered_licenses = []
            for row in to_insert_licenses:
                filtered_licenses.append(tuple(row[i] for i in col_indices))

            placeholders = ", ".join(["?"] * len(insert_cols))
            col_names = ", ".join(insert_cols)

            conn.executemany(
                f"INSERT INTO licenses ({col_names}) VALUES ({placeholders})",
                filtered_licenses,
            )
            conn.executemany(
                "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
                to_insert_index,
            )
            conn.execute(
                "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
                ("last_check_datetime", "2099-01-01T00:00:00"),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    print(f"[{LABEL}] DB ready. Running queries …", file=sys.stderr, flush=True)

    matcher = AggregatedLicenseMatcher(db_path, enable_java=False)
    matcher.match("MIT License")  # warm up

    tracemalloc.start()
    tracemalloc.clear_traces()
    t_start: float = time.perf_counter()

    stats: dict[str, dict[str, dict[str, int]]] = {
        "type_1": {},
        "type_2": {},
        "type_3": {},
        "type_4": {},
        "type_5": {},
    }
    global_counts = {"total_returned": 0, "correct_returned": 0}
    failures: list[dict[str, Any]] = []

    base_dir = Path(__file__).parent.parent / "tests" / "fixtures"

    print("Running Type 1...", file=sys.stderr, flush=True)
    # Type 1
    t1_path = base_dir / "license-id" / "license_ids.json"
    if t1_path.exists():
        with open(t1_path, "r", encoding="utf-8") as f:
            t1_data = json.load(f)
        if IS_VERIFY:
            t1_data = t1_data[:2]

        fields_t1 = [
            "id_verbatim",
            "id_deprecated",
            "id_space",
            "id_casing",
            "id_punct",
            "id_distorted",
        ]
        for fld in fields_t1:
            stats["type_1"][fld] = init_stat()

        for item in t1_data:
            true_id = item["license_id"]
            for fld in fields_t1:
                text = item.get(fld)
                if text:
                    check_match(
                        true_id,
                        text,
                        matcher,
                        stats["type_1"][fld],
                        failures,
                        "type_1",
                        fld,
                        global_counts,
                    )

    print("Running Type 2...", file=sys.stderr, flush=True)
    # Type 2
    t2_path = base_dir / "license-name" / "license_names.json"
    if t2_path.exists():
        with open(t2_path, "r", encoding="utf-8") as f:
            t2_data = json.load(f)
        if IS_VERIFY:
            t2_data = t2_data[:2]

        fields = [
            "name_verbatim",
            "name_space",
            "name_casing",
            "name_punct",
            "name_distored",
        ]
        for fld in fields:
            stats["type_2"][fld] = init_stat()

        for item in t2_data:
            true_id = item["license_id"]
            for fld in fields:
                text = item.get(fld)
                if text:
                    check_match(
                        true_id,
                        text,
                        matcher,
                        stats["type_2"][fld],
                        failures,
                        "type_2",
                        fld,
                        global_counts,
                    )

    print("Running Type 3...", file=sys.stderr, flush=True)
    # Type 3
    t3_dir = base_dir / "license-text-short"
    if t3_dir.exists():
        t3_files = sorted(t3_dir.glob("*.json"))
        if IS_VERIFY:
            t3_files = t3_files[:2]

        for fp in t3_files:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            true_id = data["license_id"]
            count = 0
            for k, v in data.items():
                if k.startswith("license_text_short_") and isinstance(v, str):
                    if IS_VERIFY and count >= 2:
                        continue
                    if k not in stats["type_3"]:
                        stats["type_3"][k] = init_stat()
                    check_match(
                        true_id,
                        v,
                        matcher,
                        stats["type_3"][k],
                        failures,
                        "type_3",
                        k,
                        global_counts,
                    )
                    count += 1

    print("Running Type 4...", file=sys.stderr, flush=True)
    # Type 4
    t4_dir = base_dir / "license-text-long"
    if t4_dir.exists():
        t4_files = sorted(t4_dir.glob("*.json"))
        if IS_VERIFY:
            t4_files = t4_files[:2]

        for fp in t4_files:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            true_id = data["license_id"]

            if "verbatim" not in stats["type_4"]:
                stats["type_4"]["verbatim"] = init_stat()
            check_match(
                true_id,
                data["license_text"],
                matcher,
                stats["type_4"]["verbatim"],
                failures,
                "type_4",
                "verbatim",
                global_counts,
            )

            for rate in ["01", "02", "05", "10", "20"]:
                k = f"license_text_long_distorted_{rate}"
                v = data.get(k)
                if v:
                    if rate not in stats["type_4"]:
                        stats["type_4"][rate] = init_stat()
                    check_match(
                        true_id,
                        v,
                        matcher,
                        stats["type_4"][rate],
                        failures,
                        "type_4",
                        rate,
                        global_counts,
                    )

    print("Running Type 5...", file=sys.stderr, flush=True)
    # Type 5
    t5_dir = base_dir / "mixed-content"
    if t5_dir.exists():
        t5_subdirs = sorted([d for d in t5_dir.iterdir() if d.is_dir()])
        if IS_VERIFY:
            t5_subdirs = t5_subdirs[:2]

        if "mixed" not in stats["type_5"]:
            stats["type_5"]["mixed"] = init_stat()

        for d in t5_subdirs:
            print(f"  Type 5: processing dir {d.name}", file=sys.stderr, flush=True)
            true_id = safe_to_canon.get(d.name)
            if not true_id:
                continue

            count = 0
            for fp in d.iterdir():
                if fp.is_file():
                    if IS_VERIFY and count >= 2:
                        break
                    with open(fp, "r", encoding="utf-8") as inner_f:
                        text = inner_f.read()
                    check_match(
                        true_id,
                        text,
                        matcher,
                        stats["type_5"]["mixed"],
                        failures,
                        "type_5",
                        "mixed",
                        global_counts,
                    )
                    count += 1

    wall_time: float = time.perf_counter() - t_start
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_q: int = 0
    for t_dict in stats.values():
        for s_dict in t_dict.values():
            total_q += s_dict["total"]

    print(f"[{LABEL}] Done in {wall_time:.1f}s", file=sys.stderr, flush=True)

    result: dict[str, Any] = {
        "label": LABEL,
        "stats": stats,
        "total_q": total_q,
        "total_returned": global_counts["total_returned"],
        "correct_returned": global_counts["correct_returned"],
        "wall_time": wall_time,
        "peak_mem_mb": peak_mem / 1024 / 1024,
        "avg_mem_mb": current_mem / 1024 / 1024,
        "failures_sample": failures[:10],
    }

    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{BENCHMARK_NAME}_{LABEL}_{TIMESTAMP}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
