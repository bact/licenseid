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
import tarfile
import tempfile
import time
import tracemalloc
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from licenseid.types import MatchRequest

if len(sys.argv) < 5:
    print(
        "Usage: python bench_single.py <src_path> <label> <benchmark_name> <timestamp>"
        " [--tarball PATH] [--verify]"
    )
    sys.exit(1)

SRC_PATH: str = sys.argv[1]
LABEL: str = sys.argv[2]
BENCHMARK_NAME: str = sys.argv[3]
TIMESTAMP: str = sys.argv[4]
IS_VERIFY: bool = "--verify" in sys.argv

_TARBALL_IDX: Optional[int] = next(
    (i for i, a in enumerate(sys.argv) if a == "--tarball"), None
)
TARBALL_PATH: Optional[Path] = (
    Path(sys.argv[_TARBALL_IDX + 1]) if _TARBALL_IDX is not None else None
)

sys.path.insert(0, SRC_PATH)
# pylint: disable=wrong-import-position
from licenseid.database import LicenseDatabase  # noqa: E402
from licenseid.matcher import AggregatedLicenseMatcher  # noqa: E402
from licenseid.normalize import normalize_text  # noqa: E402


def init_stat() -> dict[str, int]:
    return {
        "total": 0,
        "top1": 0,
        "top3": 0,
        "top5": 0,
        "top10": 0,
        "top20": 0,
        "top30": 0,
        "top40": 0,
        "top50": 0,
    }


def init_tier_stat() -> dict[str, int]:
    """Per-tier recall counters for a single subcat."""
    return {
        "total": 0,
        "tier0": 0,
        "tier05": 0,
        "tier1": 0,
        "tier2": 0,
        "missed": 0,
    }


def check_match(
    true_id: str,
    text: str,
    matcher: "InstrumentedMatcher",
    stat_obj: dict[str, int],
    failures_list: list[dict[str, Any]],
    category: str,
    subcat: str,
    global_counts: dict[str, int],
    tier_stat_obj: dict[str, int],
) -> None:
    results, trace = matcher.match_traced(text, true_id)
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
    for n in (10, 20, 30, 40, 50):
        if true_id in matched_ids[:n]:
            stat_obj[f"top{n}"] += 1

    # Per-tier recall
    tier_stat_obj["total"] += 1
    tier_name = trace.get("hit_tier")
    if tier_name in ("tier0", "tier05", "tier1", "tier2"):
        tier_stat_obj[tier_name] += 1
    else:
        tier_stat_obj["missed"] += 1


class InstrumentedMatcher(AggregatedLicenseMatcher):
    """Thin subclass used only by benchmarks to record per-tier recall.

    Production behaviour is unchanged — this class adds `match_traced`,
    which calls the same private methods as `match` but records at which
    tier the correct candidate first appeared.
    """

    def match_traced(self, text: str, true_id: str) -> tuple[list[Any], dict[str, Any]]:
        """Run the full pipeline and return (results, trace).

        ``trace`` contains:
          ``hit_tier``: one of 'tier0', 'tier05', 'tier1', 'tier2', or None.
        """
        from licenseid.normalize import normalize_text  # noqa: PLC0415

        results = self.match(text)
        trace: dict[str, Any] = {"hit_tier": None}

        if not text:
            return results, trace

        # Reconstruct tier decisions in read-only order to find the first tier
        # that would have surfaced true_id, mirroring the logic in match().
        # Guards use hasattr so this works on branches that lack certain
        # attributes (e.g. 'main' does not have self.detector).

        norm_input = normalize_text(text)
        words = norm_input.split()

        # Tier 0.5: marker detection (license-marker branch only)
        marker_candidates: list[Any] = []
        if hasattr(self, "detector"):
            marker_candidates = self.detector.detect(text)
        spdx_exact = [c for c in marker_candidates if c.get("score", 0) == 1.0]
        if spdx_exact:
            if any(c["license_id"] == true_id for c in spdx_exact):
                trace["hit_tier"] = "tier05"
                return results, trace
            # exact marker fired but not for true_id; pipeline still returned
            # via marker path so we can't inspect further tiers
            return results, trace

        # Tier 0: short-text shortcut
        if len(words) < 20 and hasattr(self, "_match_short_text"):
            short = self._match_short_text(norm_input)
            if short and short[0]["score"] > 1.0:
                if any(s["license_id"] == true_id for s in short):
                    trace["hit_tier"] = "tier0"
                return results, trace

        # Tier 0.5 (non-exact markers only) — check if true_id is in marker pool
        if any(c["license_id"] == true_id for c in marker_candidates):
            trace["hit_tier"] = "tier05"
            return results, trace

        # Tier 1: FTS5 candidates
        request: "MatchRequest" = cast("MatchRequest", {"text": text})
        tier1_candidates: list[Any] = []
        if hasattr(self, "_get_candidates"):
            tier1_candidates = self._get_candidates(request, text)
        # Merge marker candidates (same as match())
        seen = {c["license_id"] for c in tier1_candidates}
        for c in marker_candidates:
            if c["license_id"] not in seen:
                tier1_candidates.append(c)
                seen.add(c["license_id"])
        if any(c["license_id"] == true_id for c in tier1_candidates):
            trace["hit_tier"] = "tier1"
            return results, trace

        # Tier 2: ranked output (final results from match())
        if any(r["license_id"] == true_id for r in results):
            trace["hit_tier"] = "tier2"

        return results, trace


def _find_tarball() -> Path:
    """Return the SPDX tarball path, preferring the newest cached version."""
    candidates = sorted(Path.home().glob(".local/share/licenseid/spdx-data-v*.tar.gz"))
    if not candidates:
        print(
            json.dumps(
                {
                    "error": "No SPDX tarball found in ~/.local/share/licenseid/."
                    " Run 'licenseid update' or pass --tarball PATH."
                }
            )
        )
        sys.exit(1)
    return candidates[-1]  # lexicographic sort → newest version last


def _build_db_from_tarball(
    tar_path: Path,
    label: str,
) -> tuple[str, list[tuple[Any, ...]], list[tuple[str, str]], dict[str, str]]:
    """Extract the SPDX tarball and return DB insertion data.

    Returns:
        db_path: in-memory SQLite URI.
        to_insert_licenses: rows for the ``licenses`` table.
        to_insert_index: rows for the ``license_index`` table.
        safe_to_canon: filesystem-safe licence ID → canonical licence ID.
    """
    to_insert_licenses: list[tuple[Any, ...]] = []
    to_insert_index: list[tuple[str, str]] = []
    safe_to_canon: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=tmp_dir)  # noqa: S202

        root_dir = next(Path(tmp_dir).iterdir())
        lic_json_path = root_dir / "json" / "licenses.json"
        with open(lic_json_path, "r", encoding="utf-8") as fh:
            lic_data = json.load(fh)

        licenses_list: list[dict[str, Any]] = lic_data.get("licenses", [])

        # Pre-compute active IDs to resolve superseded_by at index time,
        # mirroring the logic in LicenseDatabase._update_db_records().
        active_ids: set[str] = {
            lic["licenseId"]
            for lic in licenses_list
            if not lic.get("isDeprecatedLicenseId", False)
        }

        for lic in licenses_list:
            license_id: str = lic["licenseId"]
            text_path = root_dir / "text" / f"{license_id}.txt"
            if not text_path.exists():
                continue

            with open(text_path, "r", encoding="utf-8") as fh:
                raw_text = fh.read()

            is_deprecated: bool = bool(lic.get("isDeprecatedLicenseId", False))
            superseded_by: Optional[str] = None
            if is_deprecated and license_id.endswith("+"):
                or_later = license_id[:-1] + "-or-later"
                if or_later in active_ids:
                    superseded_by = or_later

            is_osi: bool = bool(lic.get("isOsiApproved", False))
            is_fsf: bool = bool(lic.get("isFsfLibre", False))
            # Use a modest baseline; popularity CSV is not downloaded for
            # benchmarks.  The exact pop_score does not affect recall metrics.
            pop_score: int = 100 if (is_osi or is_fsf) else 1
            is_high_usage: bool = is_osi or is_fsf

            normalized = normalize_text(raw_text)
            word_count = len(normalized.split())

            to_insert_licenses.append(
                (
                    license_id,
                    lic.get("name", ""),
                    True,  # is_spdx
                    is_osi,
                    is_fsf,
                    is_high_usage,
                    is_deprecated,
                    superseded_by,
                    pop_score,
                    word_count,
                )
            )
            to_insert_index.append((license_id, normalized))
            safe_to_canon[license_id.replace(" ", "_").replace("/", "_")] = license_id

    db_name = f"bench_{label}_{uuid.uuid4().hex}"
    db_path = f"file:{db_name}?mode=memory&cache=shared"
    return db_path, to_insert_licenses, to_insert_index, safe_to_canon


def main() -> None:
    # pylint: disable=too-many-locals,too-many-statements
    tar_path: Path = TARBALL_PATH if TARBALL_PATH is not None else _find_tarball()

    print(
        f"[{LABEL}] Building DB from {tar_path.name} …",
        file=sys.stderr,
        flush=True,
    )

    db_path, to_insert_licenses, to_insert_index, safe_to_canon = (
        _build_db_from_tarball(tar_path, LABEL)
    )

    db_manager = LicenseDatabase(db_path)
    _ = db_manager

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

    print(
        f"[{LABEL}] DB ready ({len(to_insert_licenses)} licences). Running queries …",
        file=sys.stderr,
        flush=True,
    )

    matcher = InstrumentedMatcher(db_path, enable_java=False)
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
    tier_stats: dict[str, dict[str, dict[str, int]]] = {
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
            tier_stats["type_1"][fld] = init_tier_stat()

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
                        tier_stats["type_1"][fld],
                    )

        t1_total = sum(s["total"] for s in stats["type_1"].values())
        print(f"Finished Type 1 ({t1_total} queries)", file=sys.stderr, flush=True)

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
            tier_stats["type_2"][fld] = init_tier_stat()

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
                        tier_stats["type_2"][fld],
                    )

        t2_total = sum(s["total"] for s in stats["type_2"].values())
        print(f"Finished Type 2 ({t2_total} queries)", file=sys.stderr, flush=True)

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
                        tier_stats["type_3"][k] = init_tier_stat()
                    check_match(
                        true_id,
                        v,
                        matcher,
                        stats["type_3"][k],
                        failures,
                        "type_3",
                        k,
                        global_counts,
                        tier_stats["type_3"][k],
                    )
                    count += 1

        t3_total = sum(s["total"] for s in stats["type_3"].values())
        print(f"Finished Type 3 ({t3_total} queries)", file=sys.stderr, flush=True)

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
                tier_stats["type_4"]["verbatim"] = init_tier_stat()
            check_match(
                true_id,
                data["license_text"],
                matcher,
                stats["type_4"]["verbatim"],
                failures,
                "type_4",
                "verbatim",
                global_counts,
                tier_stats["type_4"]["verbatim"],
            )

            for rate in ["01", "02", "05", "10", "20"]:
                k = f"license_text_long_distorted_{rate}"
                v = data.get(k)
                if v:
                    if rate not in stats["type_4"]:
                        stats["type_4"][rate] = init_stat()
                        tier_stats["type_4"][rate] = init_tier_stat()
                    check_match(
                        true_id,
                        v,
                        matcher,
                        stats["type_4"][rate],
                        failures,
                        "type_4",
                        rate,
                        global_counts,
                        tier_stats["type_4"][rate],
                    )

        t4_total = sum(s["total"] for s in stats["type_4"].values())
        print(f"Finished Type 4 ({t4_total} queries)", file=sys.stderr, flush=True)

    print("Running Type 5...", file=sys.stderr, flush=True)
    # Type 5
    t5_dir = base_dir / "mixed-content"
    if t5_dir.exists():
        t5_subdirs = sorted([d for d in t5_dir.iterdir() if d.is_dir()])
        if IS_VERIFY:
            t5_subdirs = t5_subdirs[:2]

        if "mixed" not in stats["type_5"]:
            stats["type_5"]["mixed"] = init_stat()
            tier_stats["type_5"]["mixed"] = init_tier_stat()

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
                        tier_stats["type_5"]["mixed"],
                    )
                    count += 1

        t5_total = sum(s["total"] for s in stats["type_5"].values())
        print(f"Finished Type 5 ({t5_total} queries)", file=sys.stderr, flush=True)

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
        "tier_stats": tier_stats,
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
