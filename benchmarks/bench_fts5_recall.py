#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""FTS5 dual-query recall benchmark.

Measures Tier 1 (FTS5) recall for head-only and tail-only queries
independently at four target character sizes (700, 800, 900, 1000 chars).

The 4×4 pairwise union recall matrix is computed entirely in this script:
head_M candidates ∪ tail_N candidates for each (M, N) pair.  No
pre-combined fixtures are needed — head and tail are always queried
separately and their candidate *sets* are unioned here.

This script is intentionally standalone and focused on a single question:
how well does FTS5 surface the correct licence when given only a head or
tail slice, and what does taking their union buy us?

Usage::

    python bench_fts5_recall.py <src_path> <label> <timestamp> [--verify]

Arguments:

    src_path   Absolute path to the ``src/`` directory of the branch under
               test (inserted into ``sys.path`` so the correct code is used).
    label      Short string identifying the branch/variant (used in output
               filenames and the JSON ``label`` field).
    timestamp  ISO-8601 timestamp string (e.g. ``20260507T120000Z``).
    --verify   Quick-check mode: limits to the first 5 fixtures and skips
               the JSON output file.

Reads fixtures from ``tests/fixtures/license-text-short/``.  Run
``python scripts/generate_fixtures.py --types 3 [--full-coverage]`` first
to generate (or regenerate) those fixtures.

Output JSON is written to ``benchmarks/outputs/`` and also echoed to
stdout.
"""

import json
import sqlite3
import sys
import time
import tracemalloc
import uuid
from pathlib import Path
from statistics import mean, median, quantiles
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from licenseid.types import CandidateMatch

# ---------------------------------------------------------------------------
# CLI arguments (parsed before imports so errors are reported clearly)
# ---------------------------------------------------------------------------
if len(sys.argv) < 4:
    print(
        "Usage: python bench_fts5_recall.py <src_path> <label> <timestamp> [--verify]"
    )
    sys.exit(1)

SRC_PATH: str = sys.argv[1]
LABEL: str = sys.argv[2]
TIMESTAMP: str = sys.argv[3]
IS_VERIFY: bool = "--verify" in sys.argv

# Character sizes to benchmark.  700 and 1000 exist in the current type-3
# fixtures; 800 and 900 require regenerating with the updated script.
SIZES: list[int] = [700, 800, 900, 1000]

FIXTURES_DIR: Path = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "license-text-short"
)

sys.path.insert(0, SRC_PATH)
# pylint: disable=wrong-import-position
from licenseid.database import LicenseDatabase  # noqa: E402
from licenseid.normalize import normalize_text  # noqa: E402


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _build_db(
    fixtures: list[Path],
) -> tuple["LicenseDatabase", None]:
    """Build a shared in-memory SQLite DB from short-text fixture files.

    Each fixture file supplies both the full ``license_text`` (used as the
    indexed document) and the head/tail slices (used as queries later).

    Returns the ``LicenseDatabase`` instance (keeps the connection alive for
    the duration of the benchmark).
    """
    db_name: str = f"fts5bench_{uuid.uuid4().hex}"
    db_path: str = f"file:{db_name}?mode=memory&cache=shared"
    db = LicenseDatabase(db_path)

    to_insert_licenses: list[tuple[Any, ...]] = []
    to_insert_index: list[tuple[str, str]] = []

    for fp in fixtures:
        with open(fp, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        c_id: str = data["license_id"]
        full_text: str = data.get("license_text", "")
        normalized: str = normalize_text(full_text)
        word_count: int = len(normalized.split())
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

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("BEGIN TRANSACTION")
        try:
            cursor = conn.execute("PRAGMA table_info(licenses)")
            columns: list[str] = [row[1] for row in cursor.fetchall()]
            all_cols: list[str] = [
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
            filtered_rows = [
                tuple(row[i] for i in col_indices) for row in to_insert_licenses
            ]
            ph = ", ".join(["?"] * len(insert_cols))
            cn = ", ".join(insert_cols)
            conn.executemany(
                f"INSERT INTO licenses ({cn}) VALUES ({ph})", filtered_rows
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

    return db, None


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    # quantiles(n=20)[18] is the 95th percentile
    return quantiles(values, n=20)[18]


def _init_recall_stat() -> dict[str, int]:
    return {"total": 0, "top1": 0, "top5": 0, "top10": 0, "top50": 0}


def _init_union_stat() -> dict[str, int]:
    return {"total": 0, "in_union": 0}


def _fmt_recall(s: dict[str, int]) -> dict[str, Any]:
    total = s["total"]
    if total == 0:
        return {"total": 0}
    return {
        "total": total,
        "top1": s["top1"],
        "top5": s["top5"],
        "top10": s["top10"],
        "top50": s["top50"],
        "top1_pct": round(100 * s["top1"] / total, 2),
        "top5_pct": round(100 * s["top5"] / total, 2),
        "top10_pct": round(100 * s["top10"] / total, 2),
        "top50_pct": round(100 * s["top50"] / total, 2),
    }


def _fmt_union(u: dict[str, int]) -> dict[str, Any]:
    total = u["total"]
    if total == 0:
        return {"total": 0}
    return {
        "total": total,
        "in_union": u["in_union"],
        "recall_pct": round(100 * u["in_union"] / total, 2),
    }


def _fmt_latency(values: list[float]) -> dict[str, Any]:
    if not values:
        return {}
    return {
        "n": len(values),
        "mean_ms": round(mean(values), 3),
        "median_ms": round(median(values), 3),
        "p95_ms": round(_p95(values), 3),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # pylint: disable=too-many-locals,too-many-statements
    fixtures: list[Path] = sorted(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        print(json.dumps({"error": f"No fixtures in {FIXTURES_DIR}"}))
        sys.exit(1)

    if IS_VERIFY:
        fixtures = fixtures[:5]

    print(
        f"[{LABEL}] {len(fixtures)} fixture(s), building in-memory DB …",
        file=sys.stderr,
        flush=True,
    )
    db, _ = _build_db(fixtures)
    # Warm-up: first query has cold SQLite caches
    db.search_candidates("MIT License", limit=1)

    # -------------------------------------------------------------------
    # Accumulators
    # -------------------------------------------------------------------
    head_stats: dict[int, dict[str, int]] = {n: _init_recall_stat() for n in SIZES}
    tail_stats: dict[int, dict[str, int]] = {n: _init_recall_stat() for n in SIZES}
    # union_stats[(head_size, tail_size)]
    union_stats: dict[tuple[int, int], dict[str, int]] = {
        (h, t): _init_union_stat() for h in SIZES for t in SIZES
    }
    latencies_ms: dict[str, list[float]] = {
        **{f"head_{n}": [] for n in SIZES},
        **{f"tail_{n}": [] for n in SIZES},
    }

    tracemalloc.start()
    tracemalloc.clear_traces()
    t_wall_start: float = time.perf_counter()

    for fp in fixtures:
        with open(fp, encoding="utf-8") as fh:
            data = json.load(fh)
        true_id: str = data["license_id"]

        # Query head and tail at each size; store ordered candidate ID lists
        # so union computation below needs no extra DB calls.
        head_cands: dict[int, list[str]] = {}
        tail_cands: dict[int, list[str]] = {}

        for n in SIZES:
            head_text: str = data.get(f"license_text_short_head_{n}", "")
            tail_text: str = data.get(f"license_text_short_tail_{n}", "")

            if head_text:
                t0: float = time.perf_counter()
                h_results: list["CandidateMatch"] = db.search_candidates(
                    head_text, limit=50
                )
                latencies_ms[f"head_{n}"].append((time.perf_counter() - t0) * 1000)
                h_ids: list[str] = [
                    str(c["license_id"]) for c in h_results if c.get("license_id")
                ]
                head_cands[n] = h_ids
                hs = head_stats[n]
                hs["total"] += 1
                if h_ids and h_ids[0] == true_id:
                    hs["top1"] += 1
                if true_id in h_ids[:5]:
                    hs["top5"] += 1
                if true_id in h_ids[:10]:
                    hs["top10"] += 1
                if true_id in h_ids[:50]:
                    hs["top50"] += 1

            if tail_text:
                t0 = time.perf_counter()
                t_results: list["CandidateMatch"] = db.search_candidates(
                    tail_text, limit=50
                )
                latencies_ms[f"tail_{n}"].append((time.perf_counter() - t0) * 1000)
                t_ids: list[str] = [
                    str(c["license_id"]) for c in t_results if c.get("license_id")
                ]
                tail_cands[n] = t_ids
                ts = tail_stats[n]
                ts["total"] += 1
                if t_ids and t_ids[0] == true_id:
                    ts["top1"] += 1
                if true_id in t_ids[:5]:
                    ts["top5"] += 1
                if true_id in t_ids[:10]:
                    ts["top10"] += 1
                if true_id in t_ids[:50]:
                    ts["top50"] += 1

        # 4×4 union matrix — no extra DB queries; re-uses cached candidate lists
        for h_size in SIZES:
            for t_size in SIZES:
                if h_size not in head_cands or t_size not in tail_cands:
                    continue
                us = union_stats[(h_size, t_size)]
                us["total"] += 1
                union_set: set[str] = set(head_cands[h_size]) | set(tail_cands[t_size])
                if true_id in union_set:
                    us["in_union"] += 1

    wall_time: float = time.perf_counter() - t_wall_start
    _current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # -------------------------------------------------------------------
    # Build output
    # -------------------------------------------------------------------
    result: dict[str, Any] = {
        "label": LABEL,
        "timestamp": TIMESTAMP,
        "fixture_count": len(fixtures),
        "sizes": SIZES,
        "head": {str(n): _fmt_recall(head_stats[n]) for n in SIZES},
        "tail": {str(n): _fmt_recall(tail_stats[n]) for n in SIZES},
        # Keys: "h{head_size}_t{tail_size}" — 16 entries total
        "union": {
            f"h{h}_t{t}": _fmt_union(union_stats[(h, t)]) for h in SIZES for t in SIZES
        },
        "latency_ms": {k: _fmt_latency(v) for k, v in latencies_ms.items()},
        "wall_time_s": round(wall_time, 2),
        "peak_mem_mb": round(peak_mem / 1024 / 1024, 2),
    }

    output_dir: Path = Path(__file__).parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file: Path = output_dir / f"fts5_recall_{LABEL}_{TIMESTAMP}.json"
    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(
        f"[{LABEL}] Done in {wall_time:.1f}s — output: {output_file}",
        file=sys.stderr,
        flush=True,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
