#!/usr/bin/env python3
"""Single-branch benchmark: recall, precision, speed, memory.

Usage:
    python bench_single.py <src_path> <label>

Outputs JSON to stdout. Runs completely standalone — no shared state.
"""

import json
import sqlite3
import sys
import time
import tracemalloc
import uuid
from pathlib import Path

SRC_PATH = sys.argv[1]
LABEL = sys.argv[2] if len(sys.argv) > 2 else SRC_PATH

# Fixtures from the license-marker checkout (same set for both branches)
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "license-text-long"
RATES = ["00", "02", "05"]

# ── put target branch first on sys.path ──────────────────────────────────────
sys.path.insert(0, SRC_PATH)
from licenseid.database import LicenseDatabase  # noqa: E402
from licenseid.matcher import AggregatedLicenseMatcher  # noqa: E402
from licenseid.normalize import normalize_text  # noqa: E402

# ── load fixtures ─────────────────────────────────────────────────────────────
fixtures = sorted(FIXTURES_DIR.glob("*.json"))
if not fixtures:
    print(json.dumps({"error": f"No fixtures in {FIXTURES_DIR}"}))
    sys.exit(1)

print(f"[{LABEL}] {len(fixtures)} fixtures, building DB …", file=sys.stderr, flush=True)

# ── build in-memory DB (same pattern as test_accuracy.py) ────────────────────
db_name = f"bench_{uuid.uuid4().hex}"
db_path = f"file:{db_name}?mode=memory&cache=shared"

db_manager = LicenseDatabase(db_path)  # creates schema + _keep_alive connection

to_insert_licenses = []
to_insert_index = []
for fp in fixtures:
    with open(fp) as f:
        data = json.load(f)
    normalized = normalize_text(data["license_text"])
    word_count = len(normalized.split())
    to_insert_licenses.append(
        (
            data["license_id"],
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
    to_insert_index.append((data["license_id"], normalized))

with sqlite3.connect(db_path, uri=True) as conn:
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.executemany(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre, is_high_usage, is_deprecated, superseded_by, "
            "pop_score, word_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            to_insert_licenses,
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

print(
    f"[{LABEL}] DB ready. Running {len(fixtures) * len(RATES)} queries …",
    file=sys.stderr,
    flush=True,
)

matcher = AggregatedLicenseMatcher(db_path, enable_java=False)
matcher.match("MIT License")  # warm up

# ── benchmark ─────────────────────────────────────────────────────────────────
tracemalloc.start()
tracemalloc.clear_traces()
t_start = time.perf_counter()

stats = {r: {"total": 0, "top1": 0, "top3": 0, "top5": 0} for r in RATES}
total_returned = 0
correct_returned = 0
failures = []

for fp in fixtures:
    with open(fp) as f:
        data = json.load(f)
    true_id = data["license_id"]

    for rate in RATES:
        text = (
            data["license_text"]
            if rate == "00"
            else data.get(f"license_text_long_distorted_{rate}")
        )
        if text is None:
            continue

        results = matcher.match(text)
        matched_ids = [r["license_id"] for r in results]

        stats[rate]["total"] += 1
        total_returned += len(matched_ids)
        correct_returned += sum(1 for lid in matched_ids if lid == true_id)

        if matched_ids and matched_ids[0] == true_id:
            stats[rate]["top1"] += 1
        else:
            failures.append(
                {
                    "rate": rate,
                    "true": true_id,
                    "got": matched_ids[0] if matched_ids else "NONE",
                }
            )

        if true_id in matched_ids[:3]:
            stats[rate]["top3"] += 1
        if true_id in matched_ids[:5]:
            stats[rate]["top5"] += 1

wall_time = time.perf_counter() - t_start
_, peak_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

total_q = sum(s["total"] for s in stats.values())

print(f"[{LABEL}] Done in {wall_time:.1f}s", file=sys.stderr, flush=True)

result = {
    "label": LABEL,
    "n_fixtures": len(fixtures),
    "stats": stats,
    "total_q": total_q,
    "total_returned": total_returned,
    "correct_returned": correct_returned,
    "wall_time": wall_time,
    "peak_mem_mb": peak_mem / 1024 / 1024,
    "failures_sample": failures[:10],
}
print(json.dumps(result))
